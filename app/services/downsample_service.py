"""
Downsample Service
Background worker for sensor data downsampling
Runs at 4:00 AM every day
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import device_crud as crud_device

logger = logging.getLogger(__name__)


class DownsampleService:
    """
    Sensor data downsampling service
    
    Features:
    - Downsample sensor data older than 24 hours
    - Keep one reading every 10 minutes
    - Delete intermediate readings
    - Reduces storage by 120x
    
    Schedule: Daily at 4:00 AM
    
    Example:
    - Raw data: 1 reading every 5 seconds for 24 hours = 17,280 readings/day
    - Downsampled: 1 reading every 10 minutes = 144 readings/day
    - Reduction: 17,280 / 144 = 120x
    """
    
    def __init__(self):
        """Initialize downsample service"""
        self.scheduler = AsyncIOScheduler()
        self.running = False
    
    def start(self):
        """Start downsample service"""
        try:
            # Schedule downsample job
            self.scheduler.add_job(
                self._run_downsample,
                trigger=CronTrigger(
                    hour=settings.downsample_cron_hour,
                    minute=settings.downsample_cron_minute
                ),
                id='sensor_downsample',
                name='Sensor Data Downsampling',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.running = True
            
            logger.info(f"Downsample service started (scheduled at {settings.downsample_cron_hour}:{settings.downsample_cron_minute:02d})")
            
        except Exception as e:
            logger.error(f"Error starting downsample service: {str(e)}")
            raise
    
    def stop(self):
        """Stop downsample service"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Downsample service stopped")
    
    async def _run_downsample(self):
        """
        Run sensor data downsampling
        
        Process:
        1. Get all raw sensor data older than 24 hours
        2. Group by device
        3. Keep one reading every 10 minutes
        4. Delete intermediate readings
        5. Mark kept readings as downsampled
        """
        logger.info("Starting sensor data downsampling...")
        
        db = SessionLocal()
        try:
            # Downsample data older than 24 hours
            # Keep one reading every 10 minutes
            deleted_count = crud_device.downsample_sensor_data(
                db,
                hours_old=24,
                interval_minutes=10
            )
            
            logger.info(f"Downsampling completed: deleted {deleted_count} redundant sensor readings")
            
            # Calculate statistics
            if deleted_count > 0:
                kept_count = deleted_count // 119  # Approximate (120x reduction)
                reduction_percent = (deleted_count / (deleted_count + kept_count)) * 100
                
                logger.info(
                    f"Storage reduction: {deleted_count} deleted, "
                    f"~{kept_count} kept (~{reduction_percent:.1f}% reduction)"
                )
            
        except Exception as e:
            logger.error(f"Error during downsampling: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    async def run_manual_downsample(self):
        """
        Run downsampling manually (for testing or admin trigger)
        """
        logger.info("Running manual downsampling...")
        await self._run_downsample()


# Global downsample service instance
downsample_service = DownsampleService()


# Helper functions for easy import
def start_downsample_service():
    """Start downsample service"""
    downsample_service.start()


def stop_downsample_service():
    """Stop downsample service"""
    downsample_service.stop()


async def run_manual_downsample():
    """Run downsampling manually"""
    await downsample_service.run_manual_downsample()