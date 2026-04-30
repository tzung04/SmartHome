"""
Device model
Represents individual devices (relays, sensors) on boards
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DeviceType(str, enum.Enum):
    """Device type enumeration"""
    RELAY = "relay"
    DHT11 = "dht11"
    PIR = "pir"
    LDR = "ldr"
    RC522 = "rc522"
    CAMERA = "camera"
    DOOR_LOCK = "door_lock"


class Device(Base):
    """
    Device model
    
    Represents individual IoT devices (relays, sensors, etc.)
    Devices are auto-created based on board templates
    
    Attributes:
        id: Unique identifier (UUID)
        board_id: Board UUID this device belongs to
        device_type: Device type (relay, dht11, pir, etc.)
        name: User-friendly device name
        gpio: GPIO pin number (nullable for virtual devices)
        state: Current device state (JSONB)
        position_x: X coordinate on floor plan
        position_y: Y coordinate on floor plan
        created_at: Creation timestamp
        updated_at: Last update timestamp
    
    State examples:
        - Relay: {"is_on": true}
        - DHT11: {"temperature": 25.5, "humidity": 60.2}
        - PIR: {"motion_detected": false}
        - LDR: {"light_level": 450}
        - Camera: {"resolution": "160x120", "quality": 10}
        - Door Lock: {"is_locked": true}
    
    Relationships:
        board: Board this device belongs to
        history: Device history entries
        sensor_data: Sensor data readings
        timers: Timers for this device
    """
    __tablename__ = "devices"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    board_id = Column(
        UUID(as_uuid=True),
        ForeignKey("boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    device_type = Column(
        SQLEnum(DeviceType, name='device_type'),
        nullable=False,
        index=True
    )
    
    name = Column(
        String(255),
        nullable=False
        # Default: "Thiết bị 1", "Thiết bị 2", etc.
    )
    
    gpio = Column(
        Integer
        # GPIO pin number, nullable for virtual devices (camera, rc522)
    )
    
    state = Column(
        JSONB,
        default=dict,
        nullable=False
        # Current device state stored as JSON
    )
    
    position_x = Column(
        Float
        # X coordinate on floor plan (nullable)
    )
    
    position_y = Column(
        Float
        # Y coordinate on floor plan (nullable)
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    board = relationship("Board", back_populates="devices")
    
    history = relationship(
        "DeviceHistory",
        back_populates="device",
        cascade="all, delete-orphan"
    )
    
    sensor_data = relationship(
        "SensorData",
        back_populates="device",
        cascade="all, delete-orphan"
    )
    
    timers = relationship(
        "Timer",
        back_populates="device",
        cascade="all, delete-orphan"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Device(id={self.id}, name={self.name}, type={self.device_type})>"
    
    def is_relay(self) -> bool:
        """Check if device is a relay"""
        return self.device_type == DeviceType.RELAY
    
    def is_sensor(self) -> bool:
        """Check if device is a sensor"""
        return self.device_type in [
            DeviceType.DHT11,
            DeviceType.PIR,
            DeviceType.LDR
        ]
    
    def update_state(self, new_state: dict):
        """
        Update device state
        
        Args:
            new_state: New state dictionary
        """
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)