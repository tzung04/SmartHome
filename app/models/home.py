"""
Home and HomeMember models
Manages homes and multi-user memberships
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class MemberRole(str, enum.Enum):
    """Home member role enumeration"""
    OWNER = "owner"
    MEMBER = "member"


class Home(Base):
    """
    Home model
    
    Represents a physical home/location with IoT devices
    
    Attributes:
        id: Unique identifier (UUID)
        name: Home name
        address: Physical address (optional)
        owner_id: User ID of home owner
        created_at: Creation timestamp
        updated_at: Last update timestamp
    
    Relationships:
        owner: User who owns this home
        members: Home memberships
        floors: Floors in this home
        boards: IoT boards in this home
        access_cards: RFID cards for this home
        access_logs: Access logs for this home
        timers: Timers in this home
        scenes: Scenes for this home (future)
        automations: Automations for this home (future)
    """
    __tablename__ = "homes"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    name = Column(
        String(255),
        nullable=False
    )
    
    address = Column(Text)
    
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
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
    
    owner = relationship("User", back_populates="homes")
    
    members = relationship(
        "HomeMember",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    floors = relationship(
        "Floor",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    boards = relationship(
        "Board",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    access_cards = relationship(
        "AccessCard",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    access_logs = relationship(
        "AccessLog",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    timers = relationship(
        "Timer",
        back_populates="home",
        cascade="all, delete-orphan"
    )
    
    # Future features
    # scenes = relationship("Scene", back_populates="home")
    # automations = relationship("Automation", back_populates="home")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Home(id={self.id}, name={self.name})>"


class HomeMember(Base):
    """
    Home membership model
    
    Represents user membership in a home with specific role
    
    Attributes:
        id: Unique identifier (UUID)
        home_id: Home UUID
        user_id: User UUID
        role: Member role (owner or member)
        added_at: Membership creation timestamp
    
    Relationships:
        home: Home this membership belongs to
        user: User who is member
    """
    __tablename__ = "home_members"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    home_id = Column(
        UUID(as_uuid=True),
        ForeignKey("homes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    role = Column(
        SQLEnum(MemberRole, name='member_role'),
        default=MemberRole.MEMBER,
        nullable=False
    )
    
    added_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    home = relationship("Home", back_populates="members")
    user = relationship("User", back_populates="memberships")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<HomeMember(home_id={self.home_id}, user_id={self.user_id}, role={self.role})>"
    
    def is_owner(self) -> bool:
        """Check if member is owner"""
        return self.role == MemberRole.OWNER