"""
Cleanup Service
Background worker for daily data cleanup
Runs at 3:00 AM every day
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import device_crud as crud_device
from app.crud import timer_crud as crud_timer
from app.crud import access_control_crud as crud_access_control
from app.services.storage_service import storage_service
from app.crud import pairing_session_crud as crud_pairing

logger = logging.getLogger(__name__)


class CleanupService:
    """
    Data cleanup service
    
    Features:
    - Delete device history older than 7 days
    - Delete sensor data older than 7 days
    - Delete access logs older than 7 days + images
    - Delete old timers (executed/failed/cancelled)
    - Delete expired password reset OTPs
    
    Schedule: Daily at 3:00 AM
    """
    
    def __init__(self):
        """Initialize cleanup service"""
        self.scheduler = AsyncIOScheduler()
        self.running = False
    
    def start(self):
        """Start cleanup service"""
        try:
            # Schedule cleanup job
            self.scheduler.add_job(
                self._run_cleanup,
                trigger=CronTrigger(
                    hour=settings.cleanup_cron_hour,
                    minute=settings.cleanup_cron_minute
                ),
                id='data_cleanup',
                name='Data Cleanup',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.running = True
            
            logger.info(f"Cleanup service started (scheduled at {settings.cleanup_cron_hour}:{settings.cleanup_cron_minute:02d})")
            
        except Exception as e:
            logger.error(f"Error starting cleanup service: {str(e)}")
            raise
    
    def stop(self):
        """Stop cleanup service"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Cleanup service stopped")
    
    async def _run_cleanup(self):
        """
        Run all cleanup tasks
        """
        logger.info("Starting daily cleanup...")
        
        db = SessionLocal()
        try:
            # 1. Cleanup device history
            deleted_history = crud_device.cleanup_old_history(
                db,
                days=settings.retention_days_device_history
            )
            logger.info(f"Deleted {deleted_history} device history records")
            
            # 2. Cleanup sensor data
            deleted_sensors = crud_device.cleanup_old_sensor_data(
                db,
                days=settings.retention_days_sensor_data
            )
            logger.info(f"Deleted {deleted_sensors} sensor data records")
            
            # 3. Cleanup access logs
            deleted_logs = crud_access_control.cleanup_old_logs(
                db,
                days=settings.retention_days_access_logs
            )
            logger.info(f"Deleted {deleted_logs} access log records")
            
            # 4. Cleanup access log images from storage
            deleted_images = storage_service.delete_old_access_log_images(
                days=settings.retention_days_access_logs
            )
            logger.info(f"Deleted {deleted_images} access log images")
            
            # 5. Cleanup old timers (executed/failed/cancelled older than 30 days)
            deleted_timers = crud_timer.delete_old_timers(db, days=30)
            logger.info(f"Deleted {deleted_timers} old timer records")
            
            # 6. Cleanup expired password reset OTPs
            from app.models.password_reset_model import PasswordResetOTP
            from app.models.pending_registration_model import PendingRegistration
            from datetime import datetime, timezone
            
            deleted_otps = db.query(PasswordResetOTP).filter(
                PasswordResetOTP.expires_at < datetime.now(timezone.utc)
            ).delete()
            db.commit()
            logger.info(f"Deleted {deleted_otps} expired OTPs")

            # 7. Cleanup expired pending registrations
            deleted_pending = db.query(PendingRegistration).filter(
                PendingRegistration.expires_at < datetime.now(timezone.utc)
            ).delete()
            db.commit()
            logger.info(f"Deleted {deleted_pending} expired pending registrations")

            # 8. Cleanup expired pairing sessions
            deleted_pairing = crud_pairing.cleanup_expired_sessions(db)
            logger.info(f"Deleted {deleted_pairing} expired pairing sessions")
            
            logger.info("Daily cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    async def run_manual_cleanup(self):
        """
        Run cleanup manually (for testing or admin trigger)
        """
        logger.info("Running manual cleanup...")
        await self._run_cleanup()


# Global cleanup service instance
cleanup_service = CleanupService()


# Helper functions for easy import
def start_cleanup_service():
    """Start cleanup service"""
    cleanup_service.start()


def stop_cleanup_service():
    """Stop cleanup service"""
    cleanup_service.stop()


async def run_manual_cleanup():
    """Run cleanup manually"""
    await cleanup_service.run_manual_cleanup()