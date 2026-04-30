"""
Device history and sensor data models
Tracks device state changes and sensor readings
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DeviceHistory(Base):
    """
    Device history model
    
    Tracks device state changes and actions
    Retention: 7 days
    
    Attributes:
        id: Unique identifier (UUID)
        device_id: Device UUID
        action: Action performed (e.g., 'turned_on', 'turned_off', 'state_changed')
        old_state: Previous device state (JSONB)
        new_state: New device state (JSONB)
        triggered_by: User who triggered action (nullable for automations)
        created_at: Action timestamp
    
    Relationships:
        device: Device this history belongs to
        triggered_by_user: User who triggered this action
    """
    __tablename__ = "device_history"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    action = Column(
        String(50),
        nullable=False
        # 'turned_on', 'turned_off', 'state_changed', etc.
    )
    
    old_state = Column(JSONB)
    new_state = Column(JSONB)
    
    triggered_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
        # NULL = triggered by automation/timer
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    device = relationship("Device", back_populates="history")
    triggered_by_user = relationship("User")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<DeviceHistory(device_id={self.device_id}, action={self.action}, at={self.created_at})>"


class SensorData(Base):
    """
    Sensor data model
    
    Stores sensor readings (temperature, humidity, motion, light)
    Data collected every 5 seconds
    Retention: 7 days with downsampling after 24h (keep every 10 minutes)
    
    Attributes:
        id: Unique identifier (UUID)
        device_id: Device UUID
        data: Sensor reading data (JSONB)
        is_downsampled: Whether this is a downsampled entry
        created_at: Reading timestamp
    
    Data examples:
        - DHT11: {"temperature": 25.5, "humidity": 60.2}
        - PIR: {"motion_detected": true}
        - LDR: {"light_level": 450}
    
    Relationships:
        device: Device this reading belongs to
    """
    __tablename__ = "sensor_data"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    data = Column(
        JSONB,
        nullable=False
        # Sensor reading data
    )
    
    is_downsampled = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
        # True = downsampled data (1 reading per 10 minutes)
        # False = raw data (1 reading per 5 seconds)
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    device = relationship("Device", back_populates="sensor_data")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<SensorData(device_id={self.device_id}, data={self.data}, at={self.created_at})>"