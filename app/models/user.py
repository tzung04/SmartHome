"""
User model
Handles user authentication and authorization
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration"""
    SUPER_ADMIN = "super_admin"
    USER = "user"


class User(Base):
    """
    User model for authentication and authorization
    
    Attributes:
        id: Unique identifier (UUID)
        email: User email (unique)
        hashed_password: Bcrypt hashed password
        full_name: User's full name
        role: User role (super_admin or user)
        is_active: Account active status
        is_verified: Email verification status
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    
    Relationships:
        homes: Homes where user is owner
        memberships: Home memberships
        timers: Timers created by user
        password_resets: Password reset OTPs
    """
    __tablename__ = "users"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    
    hashed_password = Column(
        String(255),
        nullable=False
    )
    
    full_name = Column(String(255))
    
    role = Column(
        SQLEnum(UserRole, name='user_role'),
        default=UserRole.USER,
        nullable=False,
        index=True
    )
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
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
    
    # Homes where user is owner
    homes = relationship(
        "Home",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    
    # Home memberships
    memberships = relationship(
        "HomeMember",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Timers created by user
    timers = relationship(
        "Timer",
        back_populates="created_by_user",
        cascade="all, delete-orphan"
    )
    
    # Password reset OTPs
    password_resets = relationship(
        "PasswordResetOTP",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    def is_super_admin(self) -> bool:
        """Check if user is super admin"""
        return self.role == UserRole.SUPER_ADMIN