"""
Timer Service 
Background worker for timer execution with FCM push notifications
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import timer as crud_timer
from app.crud import device as crud_device
from app.crud import home as crud_home
from app.services.mqtt_service import publish_device_control
from app.services.websocket_manager import manager as ws_manager
from app.services.fcm_service import (
    notify_timer_executed,
    notify_timer_executed_to_home_members
)

logger = logging.getLogger(__name__)


class TimerService:
    """
    Enhanced timer execution service with FCM notifications
    
    Features:
    - Check pending timers every second
    - Execute timers via MQTT
    - Retry logic (3 attempts, 30s interval)
    - Mark as failed after retries
    - WebSocket real-time notifications
    - FCM push notifications to home owner and members
    """
    
    def __init__(self):
        """Initialize timer service"""
        self.scheduler = AsyncIOScheduler()
        self.running = False
    
    def start(self):
        """Start timer service"""
        try:
            # Schedule timer check job
            self.scheduler.add_job(
                self._check_and_execute_timers,
                trigger=IntervalTrigger(seconds=settings.timer_check_interval),
                id='timer_executor',
                name='Timer Executor',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.running = True
            
            logger.info("Timer service started with FCM notification support")
            
        except Exception as e:
            logger.error(f"Error starting timer service: {str(e)}")
            raise
    
    def stop(self):
        """Stop timer service"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Timer service stopped")
    
    async def _check_and_execute_timers(self):
        """
        Check for pending timers and execute them
        Runs every second
        """
        db = SessionLocal()
        try:
            # Get all pending timers that should execute now
            pending_timers = crud_timer.get_pending_timers(db)
            
            if not pending_timers:
                return
            
            logger.info(f"Found {len(pending_timers)} pending timers to execute")
            
            # Execute each timer
            for timer in pending_timers:
                try:
                    await self._execute_timer(db, timer)
                except Exception as e:
                    logger.error(f"Error executing timer {timer.id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error checking timers: {str(e)}")
        finally:
            db.close()
    
    async def _execute_timer(self, db, timer):
        """
        Execute a single timer with FCM notifications
        
        Args:
            db: Database session
            timer: Timer model instance
        """
        try:
            # Get device
            device = crud_device.get_device_by_id(db, timer.device_id)
            if not device:
                logger.error(f"Device not found for timer {timer.id}")
                crud_timer.mark_timer_failed(db, timer.id)
                return
            
            # Get board
            board = device.board
            if not board:
                logger.error(f"Board not found for timer {timer.id}")
                crud_timer.mark_timer_failed(db, timer.id)
                return
            
            # Check if board is online
            if board.status != "online":
                logger.warning(f"Board {board.id} is offline, will retry timer {timer.id}")
                
                # Check if can retry
                if timer.can_retry():
                    crud_timer.reschedule_timer_retry(db, timer.id, delay_seconds=30)
                    logger.info(f"Timer {timer.id} rescheduled (retry {timer.retry_count + 1}/3)")
                else:
                    # Max retries reached - SEND FAILURE NOTIFICATIONS
                    logger.error(f"Timer {timer.id} failed after {timer.retry_count} retries")
                    crud_timer.mark_timer_failed(db, timer.id)
                    
                    # Notify WebSocket
                    if board.home_id:
                        await ws_manager.notify_timer_executed(
                            board.home_id,
                            timer.id,
                            device.id,
                            success=False
                        )
                    
                    # ============================================
                    # SEND FCM FAILURE NOTIFICATIONS
                    # ============================================
                    await self._send_timer_fcm_notifications(
                        db=db,
                        board=board,
                        device=device,
                        timer=timer,
                        success=False
                    )
                
                return
            
            # Execute timer via MQTT
            success = publish_device_control(
                board.mac_address,
                device.gpio,
                timer.target_state
            )
            
            if success:
                # Mark as executed
                crud_timer.mark_timer_executed(db, timer.id)
                
                # Update device state
                crud_device.update_device_state(
                    db,
                    device.id,
                    timer.target_state,
                    triggered_by=timer.created_by
                )
                
                logger.info(f"Timer {timer.id} executed successfully")
                
                # Notify WebSocket
                if board.home_id:
                    await ws_manager.notify_timer_executed(
                        board.home_id,
                        timer.id,
                        device.id,
                        success=True
                    )
                
                # ============================================
                # SEND FCM SUCCESS NOTIFICATIONS
                # ============================================
                await self._send_timer_fcm_notifications(
                    db=db,
                    board=board,
                    device=device,
                    timer=timer,
                    success=True
                )
            else:
                logger.error(f"Failed to send MQTT command for timer {timer.id}")
                
                # Retry logic
                if timer.can_retry():
                    crud_timer.reschedule_timer_retry(db, timer.id, delay_seconds=30)
                    logger.info(f"Timer {timer.id} rescheduled after MQTT failure (retry {timer.retry_count + 1}/3)")
                else:
                    crud_timer.mark_timer_failed(db, timer.id)
                    
                    # Notify WebSocket
                    if board.home_id:
                        await ws_manager.notify_timer_executed(
                            board.home_id,
                            timer.id,
                            device.id,
                            success=False
                        )
                    
                    # Send FCM failure notifications
                    await self._send_timer_fcm_notifications(
                        db=db,
                        board=board,
                        device=device,
                        timer=timer,
                        success=False
                    )
                
        except Exception as e:
            logger.error(f"Error in timer execution: {str(e)}")
            crud_timer.mark_timer_failed(db, timer.id)
    
    async def _send_timer_fcm_notifications(
        self,
        db,
        board,
        device,
        timer,
        success: bool
    ):
        """
        Send FCM notifications for timer execution
        
        Args:
            db: Database session
            board: Board model instance
            device: Device model instance
            timer: Timer model instance
            success: Whether timer executed successfully
        """
        try:
            if not board.home_id:
                logger.debug("Board not paired to home, skipping FCM notifications")
                return
            
            # Get home details
            home = crud_home.get_home_by_id(db, board.home_id)
            if not home:
                logger.warning(f"Home not found: {board.home_id}")
                return
            
            device_name = device.name or f"Device {device.id}"
            home_name = home.name
            timer_id = str(timer.id)
            
            # ============================================
            # SEND TO HOME OWNER
            # ============================================
            if home.owner and home.owner.fcm_token:
                notification_sent = notify_timer_executed(
                    fcm_token=home.owner.fcm_token,
                    device_name=device_name,
                    success=success,
                    timer_id=timer_id,
                    home_name=home_name
                )
                
                if notification_sent:
                    logger.info(
                        f"Sent timer {'success' if success else 'failure'} "
                        f"notification to owner for timer {timer.id}"
                    )
                else:
                    logger.warning(
                        f"Failed to send notification to owner for timer {timer.id}"
                    )
            
            # ============================================
            # SEND TO HOME MEMBERS (with FCM tokens)
            # ============================================
            members_with_fcm = crud_home.get_home_members_with_fcm(db, board.home_id)
            
            if members_with_fcm:
                member_tokens = [
                    m.user.fcm_token 
                    for m in members_with_fcm 
                    if m.user.fcm_token
                ]
                
                if member_tokens:
                    success_count = notify_timer_executed_to_home_members(
                        fcm_tokens=member_tokens,
                        device_name=device_name,
                        success=success,
                        timer_id=timer_id,
                        home_name=home_name
                    )
                    
                    logger.info(
                        f"Sent timer {'success' if success else 'failure'} "
                        f"notification to {success_count}/{len(member_tokens)} members"
                    )
            
        except Exception as e:
            logger.error(f"Error sending timer FCM notifications: {str(e)}")


# Global timer service instance
timer_service = TimerService()


# Helper functions for easy import
def start_timer_service():
    """Start timer service"""
    timer_service.start()


def stop_timer_service():
    """Stop timer service"""
    timer_service.stop()