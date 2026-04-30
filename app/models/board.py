"""
Board model
Represents IoT boards (ESP8266, ESP32-CAM)
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class BoardStatus(str, enum.Enum):
    """Board status enumeration"""
    UNPAIRED = "unpaired"
    PAIRED = "paired"
    ONLINE = "online"
    OFFLINE = "offline"


class Board(Base):
    """
    IoT Board model
    
    Represents ESP8266/ESP32 boards with devices
    
    Attributes:
        id: Unique identifier (UUID)
        mac_address: Board MAC address (unique identifier)
        board_type: Board type (e.g., 'ESP8266_CONTROL_V1', 'ESP32_ACCESS_V1')
        home_id: Home UUID (nullable for unpaired boards)
        room_id: Room UUID (nullable)
        name: User-friendly board name
        firmware_version: Current firmware version
        status: Board status (unpaired/paired/online/offline)
        last_seen: Last heartbeat timestamp
        paired_at: When board was paired
        created_at: Board registration timestamp
        updated_at: Last update timestamp
    
    Relationships:
        home: Home this board belongs to
        room: Room this board is in
        devices: Devices on this board
    """
    __tablename__ = "boards"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    mac_address = Column(
        String(17),  # AA:BB:CC:DD:EE:FF format
        unique=True,
        nullable=False,
        index=True
    )
    
    board_type = Column(
        String(50),
        nullable=False
        # 'ESP8266_CONTROL_V1', 'ESP8266_SENSOR_V1', 'ESP32_ACCESS_V1'
    )
    
    home_id = Column(
        UUID(as_uuid=True),
        ForeignKey("homes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    name = Column(
        String(255)
        # User-friendly name, defaults to board type name
    )
    
    firmware_version = Column(
        String(20)
        # Semantic version string (e.g., "1.0.1")
    )
    
    status = Column(
        SQLEnum(BoardStatus, name='board_status'),
        default=BoardStatus.UNPAIRED,
        nullable=False,
        index=True
    )
    
    last_seen = Column(
        DateTime(timezone=True)
        # Updated by heartbeat messages
    )
    
    paired_at = Column(
        DateTime(timezone=True)
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
    
    home = relationship("Home", back_populates="boards")
    room = relationship("Room", back_populates="boards")
    
    devices = relationship(
        "Device",
        back_populates="board",
        cascade="all, delete-orphan"
    )
    
    # Access logs (for ESP32_ACCESS_V1 boards)
    access_logs = relationship(
        "AccessLog",
        back_populates="board",
        cascade="all, delete-orphan"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Board(id={self.id}, mac={self.mac_address}, type={self.board_type}, status={self.status})>"
    
    def is_online(self) -> bool:
        """Check if board is online"""
        return self.status == BoardStatus.ONLINE
    
    def is_paired(self) -> bool:
        """Check if board is paired to a home"""
        return self.status in [BoardStatus.PAIRED, BoardStatus.ONLINE, BoardStatus.OFFLINE]
    
    def update_last_seen(self):
        """Update last seen timestamp (called by heartbeat)"""
        self.last_seen = datetime.now(timezone.utc)