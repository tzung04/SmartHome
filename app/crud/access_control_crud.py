"""
Access Control CRUD operations
Database queries for RFID cards and access logs
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.access_control_model import AccessCard, AccessLog, AccessResult


# ============================================
# ACCESS CARD - CREATE
# ============================================

def create_access_card(
    db: Session,
    home_id: UUID,
    card_uid: str,
    owner_name: str,
    owner_user_id: Optional[UUID] = None,
    valid_until: Optional[datetime] = None
) -> AccessCard:
    """Create access card"""
    db_card = AccessCard(
        home_id=home_id,
        card_uid=card_uid,
        owner_name=owner_name,
        owner_user_id=owner_user_id,
        valid_until=valid_until,
        is_active=True
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card


# ============================================
# ACCESS CARD - READ
# ============================================

def get_card_by_id(db: Session, card_id: UUID) -> Optional[AccessCard]:
    """Get card by ID"""
    return db.query(AccessCard).filter(AccessCard.id == card_id).first()


def get_card_by_uid(db: Session, card_uid: str) -> Optional[AccessCard]:
    """Get card by UID"""
    return db.query(AccessCard).filter(AccessCard.card_uid == card_uid).first()


def get_home_cards(
    db: Session,
    home_id: UUID,
    is_active: Optional[bool] = None
) -> list[AccessCard]:
    """Get all cards for a home"""
    query = db.query(AccessCard).filter(AccessCard.home_id == home_id)
    
    if is_active is not None:
        query = query.filter(AccessCard.is_active == is_active)
    
    return query.order_by(AccessCard.created_at.desc()).all()


def get_user_cards(db: Session, user_id: UUID) -> list[AccessCard]:
    """Get all cards owned by a user"""
    return db.query(AccessCard).filter(
        AccessCard.owner_user_id == user_id
    ).order_by(AccessCard.created_at.desc()).all()


def is_card_valid(db: Session, card_uid: str) -> tuple[bool, Optional[AccessCard]]:
    """
    Check if card is valid for access
    
    Returns:
        Tuple of (is_valid, card)
    """
    card = get_card_by_uid(db, card_uid)
    
    if not card:
        return False, None
    
    if not card.is_active:
        return False, card
    
    now = datetime.now(timezone.utc)
    
    if now < card.valid_from:
        return False, card
    
    if card.valid_until and now > card.valid_until:
        return False, card
    
    return True, card


# ============================================
# ACCESS CARD - UPDATE
# ============================================

def update_card(
    db: Session,
    card_id: UUID,
    owner_name: Optional[str] = None,
    valid_until: Optional[datetime] = None
) -> Optional[AccessCard]:
    """Update card information"""
    db_card = get_card_by_id(db, card_id)
    if not db_card:
        return None
    
    if owner_name is not None:
        db_card.owner_name = owner_name
    
    if valid_until is not None:
        db_card.valid_until = valid_until
    
    db.commit()
    db.refresh(db_card)
    return db_card


def deactivate_card(db: Session, card_id: UUID) -> Optional[AccessCard]:
    """Deactivate card"""
    db_card = get_card_by_id(db, card_id)
    if not db_card:
        return None
    
    db_card.is_active = False
    db.commit()
    db.refresh(db_card)
    return db_card


def activate_card(db: Session, card_id: UUID) -> Optional[AccessCard]:
    """Activate card"""
    db_card = get_card_by_id(db, card_id)
    if not db_card:
        return None
    
    db_card.is_active = True
    db.commit()
    db.refresh(db_card)
    return db_card


# ============================================
# ACCESS CARD - DELETE
# ============================================

def delete_card(db: Session, card_id: UUID) -> bool:
    """Delete card"""
    db_card = get_card_by_id(db, card_id)
    if not db_card:
        return False
    
    db.delete(db_card)
    db.commit()
    return True


# ============================================
# ACCESS LOG - CREATE
# ============================================

def create_access_log(
    db: Session,
    board_id: UUID,
    card_uid: str,
    result: AccessResult,
    image_url: Optional[str] = None
) -> AccessLog:
    """Create access log entry"""
    # Try to find card by UID
    card = get_card_by_uid(db, card_uid)
    card_id = card.id if card else None
    
    db_log = AccessLog(
        board_id=board_id,
        card_uid=card_uid,
        card_id=card_id,
        result=result,
        image_url=image_url
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


# ============================================
# ACCESS LOG - READ
# ============================================

def get_log_by_id(db: Session, log_id: UUID) -> Optional[AccessLog]:
    """Get log by ID"""
    return db.query(AccessLog).filter(AccessLog.id == log_id).first()


def get_home_logs(
    db: Session,
    home_id: UUID,
    skip: int = 0,
    limit: int = 50,
    result: Optional[AccessResult] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> tuple[list[AccessLog], int]:
    """
    Get access logs for a home (paginated)
    
    Returns:
        Tuple of (logs list, total count)
    """
    from app.models.board_model import Board
    
    query = db.query(AccessLog).join(Board).filter(Board.home_id == home_id)
    
    # Apply filters
    if result:
        query = query.filter(AccessLog.result == result)
    
    if start_time:
        query = query.filter(AccessLog.created_at >= start_time)
    
    if end_time:
        query = query.filter(AccessLog.created_at <= end_time)
    
    total = query.count()
    logs = query.order_by(AccessLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return logs, total


def get_board_logs(
    db: Session,
    board_id: UUID,
    skip: int = 0,
    limit: int = 50
) -> tuple[list[AccessLog], int]:
    """Get logs for a specific board"""
    query = db.query(AccessLog).filter(AccessLog.board_id == board_id)
    
    total = query.count()
    logs = query.order_by(AccessLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return logs, total


def get_card_logs(
    db: Session,
    card_id: UUID,
    skip: int = 0,
    limit: int = 50
) -> tuple[list[AccessLog], int]:
    """Get logs for a specific card"""
    query = db.query(AccessLog).filter(AccessLog.card_id == card_id)
    
    total = query.count()
    logs = query.order_by(AccessLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return logs, total


# ============================================
# ACCESS LOG - UPDATE
# ============================================

def update_log_image(db: Session, log_id: UUID, image_url: str) -> Optional[AccessLog]:
    """Update access log image URL"""
    db_log = get_log_by_id(db, log_id)
    if not db_log:
        return None
    
    db_log.image_url = image_url
    db.commit()
    db.refresh(db_log)
    return db_log


# ============================================
# ACCESS LOG - DELETE
# ============================================

def delete_log(db: Session, log_id: UUID) -> bool:
    """Delete access log"""
    db_log = get_log_by_id(db, log_id)
    if not db_log:
        return False
    
    db.delete(db_log)
    db.commit()
    return True


def cleanup_old_logs(db: Session, days: int = 7) -> int:
    """
    Delete access logs older than specified days
    
    Args:
        db: Database session
        days: Number of days to keep
        
    Returns:
        Number of deleted records
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    deleted = db.query(AccessLog).filter(
        AccessLog.created_at < threshold
    ).delete()
    
    db.commit()
    return deleted


# ============================================
# STATISTICS
# ============================================

def count_home_cards(db: Session, home_id: UUID) -> int:
    """Get number of cards in a home"""
    return db.query(func.count(AccessCard.id)).filter(
        AccessCard.home_id == home_id
    ).scalar()


def count_active_cards(db: Session, home_id: UUID) -> int:
    """Get number of active cards in a home"""
    return db.query(func.count(AccessCard.id)).filter(
        and_(
            AccessCard.home_id == home_id,
            AccessCard.is_active == True
        )
    ).scalar()


def count_access_logs(
    db: Session,
    home_id: UUID,
    result: Optional[AccessResult] = None
) -> int:
    """Get number of access logs"""
    from app.models.board_model import Board
    
    query = db.query(func.count(AccessLog.id)).join(Board).filter(
        Board.home_id == home_id
    )
    
    if result:
        query = query.filter(AccessLog.result == result)
    
    return query.scalar()


def get_access_stats(db: Session, home_id: UUID, days: int = 7) -> dict:
    """
    Get access statistics for a home
    
    Returns:
        Dict with granted/denied/unknown counts
    """
    from app.models.board_model import Board
    
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(AccessLog).join(Board).filter(
        and_(
            Board.home_id == home_id,
            AccessLog.created_at >= threshold
        )
    )
    
    logs = query.all()
    
    stats = {
        "total": len(logs),
        "granted": sum(1 for log in logs if log.result == AccessResult.GRANTED),
        "denied": sum(1 for log in logs if log.result == AccessResult.DENIED),
        "unknown_card": sum(1 for log in logs if log.result == AccessResult.UNKNOWN_CARD),
        "period_days": days
    }
    
    return stats