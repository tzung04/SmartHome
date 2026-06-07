"""
Downsample Service
Real-time sensor data downsampling using Redis lock mechanism
"""
import logging
from uuid import UUID
import redis
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import device_crud as crud_device

logger = logging.getLogger(__name__)

class DownsampleService:
    
    def __init__(self):
        """Initialize Redis connection for downsampling lock"""
        try:
            # Sử dụng from_url để kết nối trực tiếp qua REDIS_URL
            self.redis_client = redis.Redis.from_url(
                settings.redis_url, 
                decode_responses=True
            )
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {str(e)}")
            self.redis_client = None

    def process_and_save_sensor_data(self, device_id: UUID, sensor_data: dict, interval_seconds: int = 600) -> bool:
        """
        Check Redis lock and save data if interval has passed.
        
        Args:
            device_id: UUID of the sensor device
            sensor_data: Data payload to save
            interval_seconds: Time to wait before next save (default 600s = 10 mins)
            
        Returns:
            True if data was saved, False if skipped
        """
        if not self.redis_client:
            logger.error("Redis client not initialized. Skipping downsample.")
            return False

        redis_key = f"sensor_lock:{str(device_id)}"
        
        try:
            # Chỉ trả về True nếu key chưa tồn tại, đồng thời set thời gian sống (TTL)
            is_time_to_save = self.redis_client.set(
                name=redis_key, 
                value="locked", 
                ex=interval_seconds, 
                nx=True
            )

            if is_time_to_save:
                db = SessionLocal()
                try:
                    crud_device.create_sensor_data(
                        db=db, 
                        device_id=device_id, 
                        data=sensor_data,
                        is_downsampled=True 
                    )
                    logger.debug(f"Saved downsampled data for sensor {device_id}")
                    return True
                finally:
                    db.close()
                    
            return False
            
        except Exception as e:
            logger.error(f"Error in Redis downsample process: {str(e)}")
            return False


# Global instance
downsample_service = DownsampleService()

# Helper function 
def process_and_save_sensor_data(device_id: UUID, sensor_data: dict, interval_seconds: int = 600) -> bool:
    return downsample_service.process_and_save_sensor_data(device_id, sensor_data, interval_seconds)
