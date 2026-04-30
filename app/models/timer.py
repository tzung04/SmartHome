"""
Timer model
Scheduled device actions with retry logic
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class TimerStatus(str, enum.Enum):
    """Timer status enumeration"""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Timer(Base):
    """
    Timer model
    
    Schedules device actions for future execution
    Server-side execution with retry logic (3 attempts, 30s interval)
    
    Attributes:
        id: Unique identifier (UUID)
        device_id: Device UUID to control
        created_by: User UUID who created timer
        target_state: Desired device state (JSONB)
        execute_at: When to execute timer
        status: Timer status (pending/executed/failed/cancelled)
        retry_count: Number of retry attempts
        executed_at: When timer was executed
        created_at: Timer creation timestamp
    
    Target state examples:
        - Relay: {"is_on": true}
        - Door lock: {"is_locked": false}
    
    Relationships:
        device: Device to control
        created_by_user: User who created timer
        home: Home this timer belongs to (via device)
    """
    __tablename__ = "timers"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    target_state = Column(
        JSONB,
        nullable=False
        # Desired state to set when timer executes
    )
    
    execute_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
        # When to execute this timer
    )
    
    status = Column(
        SQLEnum(TimerStatus, name='timer_status'),
        default=TimerStatus.PENDING,
        nullable=False,
        index=True
    )
    
    retry_count = Column(
        Integer,
        default=0,
        nullable=False
        # Number of retry attempts (max 3)
    )
    
    executed_at = Column(
        DateTime(timezone=True)
        # When timer was successfully executed
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    device = relationship("Device", back_populates="timers")
    created_by_user = relationship("User", back_populates="timers")
    
    # For convenience - access home via device.board.home
    @property
    def home(self):
        """Get home this timer belongs to"""
        if self.device and self.device.board:
            return self.device.board.home
        return None
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Timer(id={self.id}, device_id={self.device_id}, execute_at={self.execute_at}, status={self.status})>"
    
    def is_pending(self) -> bool:
        """Check if timer is pending execution"""
        return self.status == TimerStatus.PENDING
    
    def should_execute(self) -> bool:
        """Check if timer should be executed now"""
        return (
            self.status == TimerStatus.PENDING and
            datetime.now(timezone.utc) >= self.execute_at
        )
    
    def can_retry(self) -> bool:
        """Check if timer can be retried"""
        return self.retry_count < 3
    
    def mark_executed(self):
        """Mark timer as successfully executed"""
        self.status = TimerStatus.EXECUTED
        self.executed_at = datetime.now(timezone.utc)
    
    def mark_failed(self):
        """Mark timer as failed after all retries"""
        self.status = TimerStatus.FAILED
    
    def increment_retry(self):
        """Increment retry count"""
        self.retry_count += 1