"""
Timer CRUD operations
Database queries for timer management
"""
from typing import Optional, Any
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.timer import Timer, TimerStatus


# ============================================
# CREATE
# ============================================

def create_timer(
    db: Session,
    device_id: UUID,
    created_by: UUID,
    target_state: dict[str, Any],
    execute_at: datetime
) -> Timer:
    """Create timer"""
    db_timer = Timer(
        device_id=device_id,
        created_by=created_by,
        target_state=target_state,
        execute_at=execute_at,
        status=TimerStatus.PENDING
    )
    db.add(db_timer)
    db.commit()
    db.refresh(db_timer)
    return db_timer


# ============================================
# READ
# ============================================

def get_timer_by_id(db: Session, timer_id: UUID) -> Optional[Timer]:
    """Get timer by ID"""
    return db.query(Timer).filter(Timer.id == timer_id).first()


def get_device_timers(
    db: Session,
    device_id: UUID,
    status: Optional[TimerStatus] = None
) -> list[Timer]:
    """Get all timers for a device"""
    query = db.query(Timer).filter(Timer.device_id == device_id)
    
    if status:
        query = query.filter(Timer.status == status)
    
    return query.order_by(Timer.execute_at).all()


def get_home_timers(
    db: Session,
    home_id: UUID,
    status: Optional[TimerStatus] = None
) -> list[Timer]:
    """Get all timers in a home (via devices)"""
    from app.models.device import Device
    from app.models.board import Board
    
    query = db.query(Timer).join(Device).join(Board).filter(
        Board.home_id == home_id
    )
    
    if status:
        query = query.filter(Timer.status == status)
    
    return query.order_by(Timer.execute_at).all()


def get_user_timers(
    db: Session,
    user_id: UUID,
    status: Optional[TimerStatus] = None
) -> list[Timer]:
    """Get all timers created by user"""
    query = db.query(Timer).filter(Timer.created_by == user_id)
    
    if status:
        query = query.filter(Timer.status == status)
    
    return query.order_by(Timer.execute_at.desc()).all()


def get_pending_timers(db: Session) -> list[Timer]:
    """
    Get all pending timers that should be executed now
    
    Returns:
        List of timers ready for execution
    """
    now = datetime.now(timezone.utc)
    
    return db.query(Timer).filter(
        and_(
            Timer.status == TimerStatus.PENDING,
            Timer.execute_at <= now
        )
    ).order_by(Timer.execute_at).all()


def get_all_pending_timers(db: Session) -> list[Timer]:
    """Get all pending timers (for monitoring)"""
    return db.query(Timer).filter(
        Timer.status == TimerStatus.PENDING
    ).order_by(Timer.execute_at).all()


# ============================================
# UPDATE
# ============================================

def mark_timer_executed(db: Session, timer_id: UUID) -> Optional[Timer]:
    """Mark timer as successfully executed"""
    db_timer = get_timer_by_id(db, timer_id)
    if not db_timer:
        return None
    
    db_timer.status = TimerStatus.EXECUTED
    db_timer.executed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_timer)
    return db_timer


def mark_timer_failed(db: Session, timer_id: UUID) -> Optional[Timer]:
    """Mark timer as failed after all retries"""
    db_timer = get_timer_by_id(db, timer_id)
    if not db_timer:
        return None
    
    db_timer.status = TimerStatus.FAILED
    
    db.commit()
    db.refresh(db_timer)
    return db_timer


def cancel_timer(db: Session, timer_id: UUID) -> Optional[Timer]:
    """Cancel pending timer"""
    db_timer = get_timer_by_id(db, timer_id)
    if not db_timer:
        return None
    
    # Only cancel if pending
    if db_timer.status != TimerStatus.PENDING:
        return None
    
    db_timer.status = TimerStatus.CANCELLED
    
    db.commit()
    db.refresh(db_timer)
    return db_timer


def increment_timer_retry(db: Session, timer_id: UUID) -> Optional[Timer]:
    """Increment timer retry count"""
    db_timer = get_timer_by_id(db, timer_id)
    if not db_timer:
        return None
    
    db_timer.retry_count += 1
    
    db.commit()
    db.refresh(db_timer)
    return db_timer


# ============================================
# DELETE
# ============================================

def delete_timer(db: Session, timer_id: UUID) -> bool:
    """Delete timer"""
    db_timer = get_timer_by_id(db, timer_id)
    if not db_timer:
        return False
    
    db.delete(db_timer)
    db.commit()
    return True


def delete_old_timers(db: Session, days: int = 30) -> int:
    """
    Delete old executed/failed/cancelled timers
    
    Args:
        db: Database session
        days: Delete timers older than this (for executed/failed/cancelled)
        
    Returns:
        Number of deleted timers
    """
    from datetime import timedelta
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    deleted = db.query(Timer).filter(
        and_(
            Timer.status.in_([TimerStatus.EXECUTED, TimerStatus.FAILED, TimerStatus.CANCELLED]),
            Timer.created_at < threshold
        )
    ).delete()
    
    db.commit()
    return deleted


# ============================================
# STATISTICS
# ============================================

def count_timers(db: Session, status: Optional[TimerStatus] = None) -> int:
    """Get total number of timers"""
    query = db.query(func.count(Timer.id))
    
    if status:
        query = query.filter(Timer.status == status)
    
    return query.scalar()


def count_pending_timers(db: Session) -> int:
    """Get number of pending timers"""
    return count_timers(db, TimerStatus.PENDING)


def count_home_timers(db: Session, home_id: UUID, status: Optional[TimerStatus] = None) -> int:
    """Get number of timers in a home"""
    from app.models.device import Device
    from app.models.board import Board
    
    query = db.query(func.count(Timer.id)).join(Device).join(Board).filter(
        Board.home_id == home_id
    )
    
    if status:
        query = query.filter(Timer.status == status)
    
    return query.scalar()