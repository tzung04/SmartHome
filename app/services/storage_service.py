"""
Storage Service
Supabase Storage client for firmware files and access log images
"""
from typing import Optional
import base64
import hashlib
from datetime import datetime, timezone
from supabase import create_client, Client
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Supabase Storage service
    
    Buckets:
    - firmwares: Firmware .bin files for OTA updates
    - access-logs: Access log images (JPEG from ESP32-CAM)
    """
    
    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key  # Use service key for admin access
        )
        self.storage = self.client.storage
    
    # ============================================
    # FIRMWARE STORAGE
    # ============================================
    
    def upload_firmware(
        self,
        board_type: str,
        version: str,
        file_bytes: bytes
    ) -> Optional[str]:
        """
        Upload firmware file
        
        Args:
            board_type: Board type (e.g., 'ESP8266_CONTROL_V1')
            version: Firmware version (e.g., '1.0.1')
            file_bytes: Binary firmware data
            
        Returns:
            Public URL of uploaded file or None if failed
        """
        try:
            bucket = settings.storage_bucket_firmwares
            file_path = f"{board_type}/{version}.bin"
            
            # Upload file
            result = self.storage.from_(bucket).upload(
                path=file_path,
                file=file_bytes,
                file_options={
                    "content-type": "application/octet-stream",
                    "cache-control": "3600",
                    "upsert": "true"  # Overwrite if exists
                }
            )
            
            # Get public URL
            public_url = self.storage.from_(bucket).get_public_url(file_path)
            
            logger.info(f"Firmware uploaded: {file_path}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error uploading firmware: {str(e)}")
            return None
    
    def delete_firmware(self, board_type: str, version: str) -> bool:
        """
        Delete firmware file
        
        Args:
            board_type: Board type
            version: Firmware version
            
        Returns:
            True if deleted successfully
        """
        try:
            bucket = settings.storage_bucket_firmwares
            file_path = f"{board_type}/{version}.bin"
            
            self.storage.from_(bucket).remove([file_path])
            
            logger.info(f"Firmware deleted: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting firmware: {str(e)}")
            return False
    
    def get_firmware_url(self, board_type: str, version: str) -> Optional[str]:
        """
        Get public URL for firmware file
        
        Args:
            board_type: Board type
            version: Firmware version
            
        Returns:
            Public URL or None
        """
        try:
            bucket = settings.storage_bucket_firmwares
            file_path = f"{board_type}/{version}.bin"
            
            return self.storage.from_(bucket).get_public_url(file_path)
            
        except Exception as e:
            logger.error(f"Error getting firmware URL: {str(e)}")
            return None
    
    def calculate_md5(self, file_bytes: bytes) -> str:
        """
        Calculate MD5 hash of file
        
        Args:
            file_bytes: File binary data
            
        Returns:
            MD5 hash string
        """
        return hashlib.md5(file_bytes).hexdigest()
    
    # ============================================
    # ACCESS LOG IMAGES
    # ============================================
    
    def upload_access_log_image(
        self,
        board_mac: str,
        image_bytes: bytes          
    ) -> Optional[str]:
        """
        Upload access log image lên Supabase Storage.
        """
        try:
            # Generate unique filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            mac_clean = board_mac.replace(":", "")
            file_path = f"{mac_clean}/{timestamp}.jpg"

            bucket = settings.storage_bucket_access_logs

            # Upload image
            self.storage.from_(bucket).upload(
                path=file_path,
                file=image_bytes,
                file_options={
                    "content-type": "image/jpeg",
                    "cache-control": "3600"
                }
            )

            # Get public URL
            public_url = self.storage.from_(bucket).get_public_url(file_path)

            logger.info(f"Access log image uploaded: {file_path}")
            return public_url

        except Exception as e:
            logger.error(f"Error uploading access log image: {str(e)}")
            return None
    
    def delete_access_log_image(self, image_url: str) -> bool:
        """
        Delete access log image
        
        Args:
            image_url: Full public URL of image
            
        Returns:
            True if deleted successfully
        """
        try:
            # Extract file path from URL
            # URL format: https://xxx.supabase.co/storage/v1/object/public/access-logs/ABC123/20240101_120000.jpg
            bucket = settings.storage_bucket_access_logs
            
            # Parse path from URL
            url_parts = image_url.split(f"/object/public/{bucket}/")
            if len(url_parts) != 2:
                logger.error(f"Invalid image URL format: {image_url}")
                return False
            
            file_path = url_parts[1]
            
            self.storage.from_(bucket).remove([file_path])
            
            logger.info(f"Access log image deleted: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting access log image: {str(e)}")
            return False
    
    def delete_old_access_log_images(self, days: int = 7) -> int:
        """
        Delete access log images older than specified days
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of deleted images
        """
        try:
            bucket = settings.storage_bucket_access_logs
            
            # List all files
            files = self.storage.from_(bucket).list()
            
            # Calculate threshold timestamp
            from datetime import timedelta, timezone
            threshold = datetime.now(timezone.utc) - timedelta(days=days)
            
            deleted_count = 0
            
            for file_item in files:
                # Parse timestamp from filename
                try:
                    # Filename format: AABBCCDD/20240101_120000.jpg
                    parts = file_item['name'].split('/')
                    if len(parts) == 2:
                        timestamp_str = parts[1].replace('.jpg', '')
                        file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        file_date = file_date.replace(tzinfo=timezone.utc)
                        
                        if file_date < threshold:
                            self.storage.from_(bucket).remove([file_item['name']])
                            deleted_count += 1
                            
                except Exception:
                    continue
            
            logger.info(f"Deleted {deleted_count} old access log images")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting old access log images: {str(e)}")
            return 0
    
    # ============================================
    # BUCKET MANAGEMENT
    # ============================================
    
    def ensure_buckets_exist(self) -> bool:
        """
        Ensure required storage buckets exist
        
        Returns:
            True if all buckets exist or created
        """
        try:
            buckets = [
                settings.storage_bucket_firmwares,
                settings.storage_bucket_access_logs
            ]
            
            existing = self.storage.list_buckets()
            existing_names = [b.name for b in existing]
            
            for bucket_name in buckets:
                if bucket_name not in existing_names:
                    self.storage.create_bucket(
                        bucket_name,
                        options={"public": True}
                    )
                    logger.info(f"Created storage bucket: {bucket_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring buckets exist: {str(e)}")
            return False


# Global storage service instance
storage_service = StorageService()


# Helper functions for easy import
def upload_firmware(board_type: str, version: str, file_bytes: bytes) -> Optional[str]:
    """Upload firmware file"""
    return storage_service.upload_firmware(board_type, version, file_bytes)


def delete_firmware(board_type: str, version: str) -> bool:
    """Delete firmware file"""
    return storage_service.delete_firmware(board_type, version)


def upload_access_log_image(board_mac: str, image_base64: str) -> Optional[str]:
    """Upload access log image"""
    return storage_service.upload_access_log_image(board_mac, image_base64)


def delete_access_log_image(image_url: str) -> bool:
    """Delete access log image"""
    return storage_service.delete_access_log_image(image_url)