"""
Firmware model
OTA firmware management (Super Admin only)
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Firmware(Base):
    """
    Firmware model
    
    Stores firmware files for OTA updates
    Only super admins can upload/delete firmwares
    
    Attributes:
        id: Unique identifier (UUID)
        board_type: Board type this firmware is for
        version: Semantic version string (e.g., "1.0.1")
        file_url: Supabase Storage URL
        file_size_bytes: File size in bytes
        md5_hash: MD5 hash for verification
        changelog: Release notes / changelog
        uploaded_by: User UUID who uploaded
        uploaded_at: Upload timestamp
        is_active: Whether this firmware can be used for OTA
    
    Relationships:
        uploaded_by_user: User who uploaded this firmware
    """
    __tablename__ = "firmwares"
    __table_args__ = (
        UniqueConstraint('board_type', 'version', name='uq_board_type_version'),
    )
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    board_type = Column(
        String(50),
        nullable=False,
        index=True
        # 'ESP8266_CONTROL_V1', 'ESP8266_SENSOR_V1', 'ESP32_ACCESS_V1'
    )
    
    version = Column(
        String(20),
        nullable=False
        # Semantic version: '1.0.1'
    )
    
    file_url = Column(
        Text,
        nullable=False
        # Supabase Storage public URL
        # e.g., https://xxx.supabase.co/storage/v1/object/public/firmwares/ESP8266_CONTROL_V1/1.0.1.bin
    )
    
    file_size_bytes = Column(
        Integer
        # File size for progress tracking
    )
    
    md5_hash = Column(
        String(32)
        # MD5 hash for verification during OTA
    )
    
    changelog = Column(
        Text
        # Release notes / what's new
    )
    
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
        # Super admin who uploaded
    )
    
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True
        # Only active firmwares can be used for OTA
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    uploaded_by_user = relationship("User")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Firmware(id={self.id}, board_type={self.board_type}, version={self.version})>"
    
    def deactivate(self):
        """Mark firmware as inactive (soft delete)"""
        self.is_active = False