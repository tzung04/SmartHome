"""
Floor and Room models
Manages floor plans and room layouts
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Floor(Base):
    """
    Floor model
    
    Represents a floor/level in a home
    
    Attributes:
        id: Unique identifier (UUID)
        home_id: Home UUID
        name: Floor name (e.g., "Tầng 1", "Ground Floor")
        floor_number: Floor number for ordering
        created_at: Creation timestamp
    
    Relationships:
        home: Home this floor belongs to
        rooms: Rooms on this floor
    """
    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint('home_id', 'floor_number', name='uq_home_floor_number'),
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
    
    home_id = Column(
        UUID(as_uuid=True),
        ForeignKey("homes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    name = Column(
        String(255),
        nullable=False
    )
    
    floor_number = Column(
        Integer,
        nullable=False
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    home = relationship("Home", back_populates="floors")
    
    rooms = relationship(
        "Room",
        back_populates="floor",
        cascade="all, delete-orphan"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Floor(id={self.id}, name={self.name}, floor_number={self.floor_number})>"


class Room(Base):
    """
    Room model
    
    Represents a room on a floor with position and dimensions
    
    Attributes:
        id: Unique identifier (UUID)
        floor_id: Floor UUID
        name: Room name (e.g., "Phòng khách", "Living Room")
        template_type: Room template (e.g., "rectangle_4x5", "square_3x3", "l_shape")
        position_x: X coordinate on floor plan
        position_y: Y coordinate on floor plan
        width: Room width (arbitrary units)
        height: Room height (arbitrary units)
        created_at: Creation timestamp
    
    Relationships:
        floor: Floor this room belongs to
        boards: IoT boards in this room
    """
    __tablename__ = "rooms"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    floor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("floors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    name = Column(
        String(255),
        nullable=False
    )
    
    template_type = Column(
        String(50)
        # e.g., 'rectangle_3x4', 'rectangle_4x5', 'rectangle_5x6',
        # 'square_3x3', 'square_4x4', 'l_shape'
    )
    
    position_x = Column(
        Float,
        default=0.0
    )
    
    position_y = Column(
        Float,
        default=0.0
    )
    
    width = Column(
        Float,
        default=100.0
    )
    
    height = Column(
        Float,
        default=100.0
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    floor = relationship("Floor", back_populates="rooms")
    
    boards = relationship(
        "Board",
        back_populates="room"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Room(id={self.id}, name={self.name}, template={self.template_type})>"