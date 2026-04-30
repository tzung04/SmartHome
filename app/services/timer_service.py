"""
Timer Service
Background worker for timer execution with retry logic
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import timer as crud_timer
from app.crud import device as crud_device
from app.services.mqtt_service import publish_device_control
from app.services.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)


class TimerService:
    """
    Timer execution service
    
    Features:
    - Check pending timers every second
    - Execute timers via MQTT
    - Retry logic (3 attempts, 30s interval)
    - Mark as failed after retries
    - WebSocket notifications
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
            
            logger.info("Timer service started")
            
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
        Execute a single timer
        
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
                    crud_timer.increment_timer_retry(db, timer.id)
                    
                    # Schedule retry after 30 seconds
                    await asyncio.sleep(30)
                    
                    # Recursive call for retry
                    updated_timer = crud_timer.get_timer_by_id(db, timer.id)
                    if updated_timer and updated_timer.status == "pending":
                        await self._execute_timer(db, updated_timer)
                else:
                    # Max retries reached
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
            else:
                logger.error(f"Failed to send MQTT command for timer {timer.id}")
                
                # Retry logic
                if timer.can_retry():
                    crud_timer.increment_timer_retry(db, timer.id)
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
                
        except Exception as e:
            logger.error(f"Error in timer execution: {str(e)}")
            crud_timer.mark_timer_failed(db, timer.id)


# Global timer service instance
timer_service = TimerService()


# Helper functions for easy import
def start_timer_service():
    """Start timer service"""
    timer_service.start()


def stop_timer_service():
    """Stop timer service"""
    timer_service.stop()