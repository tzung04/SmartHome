"""
Password Reset OTP model
Handles password reset functionality with OTP
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PasswordResetOTP(Base):
    """
    Password reset OTP model
    
    Stores temporary OTP codes for password reset
    OTPs expire after configured time (default 10 minutes)
    
    Attributes:
        id: Unique identifier (UUID)
        email: User email requesting reset
        otp_hash: SHA256 hash of OTP code
        expires_at: OTP expiration timestamp
        attempts: Number of verification attempts
        created_at: OTP creation timestamp
    """
    __tablename__ = "password_reset_otps"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    email = Column(
        String(255),
        nullable=False,
        index=True
    )
    
    otp_hash = Column(
        String(255),
        nullable=False
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    attempts = Column(
        Integer,
        default=0,
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
    
    # Note: We don't have FK to users table because
    # we want to allow password reset even for non-existent emails
    # (for security - don't reveal if email exists)
    
    # But we can add optional relationship for convenience
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True
    )
    
    user = relationship("User", back_populates="password_resets")
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<PasswordResetOTP(email={self.email}, expires_at={self.expires_at})>"
    
    def is_expired(self) -> bool:
        """Check if OTP is expired"""
        return datetime.now(timezone.utc) > self.expires_at
    
    def increment_attempts(self):
        """Increment verification attempts"""
        self.attempts += 1