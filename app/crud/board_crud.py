"""
Board CRUD operations
Database queries for board management
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.board_model import Board, BoardStatus
from app.schemas.board_schemas import BoardUpdate


# ============================================
# CREATE
# ============================================

def create_board(
    db: Session,
    mac_address: str,
    board_type: str,
    firmware_version: Optional[str] = None
) -> Board:
    """
    Create/register new board
    
    Args:
        db: Database session
        mac_address: Board MAC address
        board_type: Board type identifier
        firmware_version: Current firmware version
        
    Returns:
        Created board
    """
    db_board = Board(
        mac_address=mac_address,
        board_type=board_type,
        firmware_version=firmware_version,
        status=BoardStatus.UNPAIRED,
        name=f"{board_type} - {mac_address[-8:]}"
    )
    db.add(db_board)
    db.commit()
    db.refresh(db_board)
    return db_board


# ============================================
# READ
# ============================================

def get_board_by_id(db: Session, board_id: UUID) -> Optional[Board]:
    """Get board by ID"""
    return db.query(Board).filter(Board.id == board_id).first()


def get_board_by_mac(db: Session, mac_address: str) -> Optional[Board]:
    """Get board by MAC address"""
    return db.query(Board).filter(Board.mac_address == mac_address).first()


def get_home_boards(db: Session, home_id: UUID) -> list[Board]:
    """Get all boards in a home"""
    return db.query(Board).filter(
        Board.home_id == home_id
    ).order_by(Board.paired_at.desc()).all()


def get_all_boards(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[BoardStatus] = None,
    board_type: Optional[str] = None
) -> tuple[list[Board], int]:
    """
    Get all boards (admin only)
    
    Returns:
        Tuple of (boards list, total count)
    """
    query = db.query(Board)
    
    # Apply filters
    if status:
        query = query.filter(Board.status == status)
    
    if board_type:
        query = query.filter(Board.board_type == board_type)
    
    total = query.count()
    boards = query.order_by(Board.created_at.desc()).offset(skip).limit(limit).all()
    
    return boards, total

def get_home_boards_by_type(db: Session, home_id: UUID, board_type: str) -> list[Board]:
    """Get all boards of a specific type in a home"""
    return db.query(Board).filter(
        Board.home_id == home_id,
        Board.board_type == board_type
    ).all()

def get_all_paired_boards(db: Session) -> List[Board]:
    """Get all paired boards"""
    return db.query(Board).filter(Board.home_id.isnot(None)).all()

def update_board_status(db: Session, board_id: UUID, status: str) -> Board:
    """Update board status"""
    board = db.query(Board).filter(Board.id == board_id).first()
    if board:
        board.status = status
        db.commit()
        db.refresh(board)
    return board


# ============================================
# UPDATE
# ============================================

def update_board(db: Session, board_id: UUID, board_update: BoardUpdate) -> Optional[Board]:
    """Update board information"""
    db_board = get_board_by_id(db, board_id)
    if not db_board:
        return None
    
    if board_update.name is not None:
        db_board.name = board_update.name
    
    db.commit()
    db.refresh(db_board)
    return db_board


def pair_board(db: Session, mac_address: str, home_id: UUID) -> Optional[Board]:
    """
    Pair board to home
    
    Args:
        db: Database session
        mac_address: Board MAC address
        home_id: Home UUID to pair to
        
    Returns:
        Paired board or None if not found
    """
    db_board = get_board_by_mac(db, mac_address)
    if not db_board:
        return None
    
    db_board.home_id = home_id
    db_board.status = BoardStatus.PAIRED
    db_board.paired_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_board)
    return db_board


def unpair_board(db: Session, board_id: UUID) -> Optional[Board]:
    """Unpair board from home"""
    db_board = get_board_by_id(db, board_id)
    if not db_board:
        return None
    
    db_board.home_id = None
    db_board.status = BoardStatus.UNPAIRED
    db_board.paired_at = None
    
    db.commit()
    db.refresh(db_board)
    return db_board


def update_board_status(db: Session, board_id: UUID, status: BoardStatus) -> Optional[Board]:
    """Update board status"""
    db_board = get_board_by_id(db, board_id)
    if not db_board:
        return None
    
    db_board.status = status
    db.commit()
    db.refresh(db_board)
    return db_board


def update_board_heartbeat(db: Session, mac_address: str) -> Optional[Board]:
    """
    Update board last_seen timestamp (heartbeat)
    
    Args:
        db: Database session
        mac_address: Board MAC address
        
    Returns:
        Updated board or None if not found
    """
    db_board = get_board_by_mac(db, mac_address)
    if not db_board:
        return None
    
    db_board.last_seen = datetime.now(timezone.utc)
    
    # Update status to online if paired
    if db_board.status in [BoardStatus.PAIRED, BoardStatus.OFFLINE]:
        db_board.status = BoardStatus.ONLINE
    
    db.commit()
    db.refresh(db_board)
    return db_board


def update_board_firmware(db: Session, board_id: UUID, new_version: str) -> Optional[Board]:
    """Update board firmware version"""
    db_board = get_board_by_id(db, board_id)
    if not db_board:
        return None
    
    db_board.firmware_version = new_version
    db.commit()
    db.refresh(db_board)
    return db_board


# ============================================
# DELETE
# ============================================

def delete_board(db: Session, board_id: UUID) -> bool:
    """Delete board (cascade deletes all devices)"""
    db_board = get_board_by_id(db, board_id)
    if not db_board:
        return False
    
    db.delete(db_board)
    db.commit()
    return True


# ============================================
# STATUS CHECKS
# ============================================

def check_offline_boards(db: Session, timeout_seconds: int = 180) -> list[Board]:
    """
    Check for boards that should be marked offline
    
    Args:
        db: Database session
        timeout_seconds: Offline timeout in seconds (default 3 minutes)
        
    Returns:
        List of boards that timed out
    """
    threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    
    offline_boards = db.query(Board).filter(
        Board.status == BoardStatus.ONLINE,
        Board.last_seen < threshold
    ).all()
    
    # Mark them as offline
    for board in offline_boards:
        board.status = BoardStatus.OFFLINE
    
    if offline_boards:
        db.commit()
    
    return offline_boards


def get_online_boards(db: Session, home_id: Optional[UUID] = None) -> list[Board]:
    """Get all online boards (optionally filtered by home)"""
    query = db.query(Board).filter(Board.status == BoardStatus.ONLINE)
    
    if home_id:
        query = query.filter(Board.home_id == home_id)
    
    return query.all()


def get_offline_boards(db: Session, home_id: Optional[UUID] = None) -> list[Board]:
    """Get all offline boards (optionally filtered by home)"""
    query = db.query(Board).filter(Board.status == BoardStatus.OFFLINE)
    
    if home_id:
        query = query.filter(Board.home_id == home_id)
    
    return query.all()


# ============================================
# STATISTICS
# ============================================

def count_boards(db: Session) -> int:
    """Get total number of boards"""
    return db.query(func.count(Board.id)).scalar()


def count_online_boards(db: Session) -> int:
    """Get number of online boards"""
    return db.query(func.count(Board.id)).filter(
        Board.status == BoardStatus.ONLINE
    ).scalar()


def count_home_boards(db: Session, home_id: UUID) -> int:
    """Get number of boards in a home"""
    return db.query(func.count(Board.id)).filter(
        Board.home_id == home_id
    ).scalar()