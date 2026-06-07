"""
Device CRUD operations
Database queries for device management
"""
from typing import Optional, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.device_model import Device, DeviceType
from app.models.history_model import DeviceHistory, SensorData
from app.schemas.device_schemas import DeviceUpdate


# ============================================
# DEVICE - CREATE
# ============================================

def create_device(
    db: Session,
    board_id: UUID,
    device_type: DeviceType,
    name: str,
    gpio: Optional[int] = None,
    state: Optional[dict] = None
) -> Device:
    """Create device"""
    db_device = Device(
        board_id=board_id,
        device_type=device_type,
        name=name,
        gpio=gpio,
        state=state or {}
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device


# ============================================
# DEVICE - READ
# ============================================

def get_device_by_id(db: Session, device_id: UUID) -> Optional[Device]:
    """Get device by ID"""
    return db.query(Device).filter(Device.id == device_id).first()


def get_board_devices(db: Session, board_id: UUID) -> list[Device]:
    """Get all devices on a board"""
    return db.query(Device).filter(
        Device.board_id == board_id
    ).order_by(Device.created_at).all()


def get_home_devices(db: Session, home_id: UUID) -> list[Device]:
    """Get all devices in a home (via boards)"""
    from app.models.board_model import Board
    
    return db.query(Device).join(Board).filter(
        Board.home_id == home_id
    ).order_by(Device.created_at).all()


def get_devices_by_type(db: Session, board_id: UUID, device_type: DeviceType) -> list[Device]:
    """Get devices of specific type on a board"""
    return db.query(Device).filter(
        Device.board_id == board_id,
        Device.device_type == device_type
    ).all()


# ============================================
# DEVICE - UPDATE
# ============================================

def update_device(db: Session, device_id: UUID, device_update: DeviceUpdate) -> Optional[Device]:
    """Update device information"""
    db_device = get_device_by_id(db, device_id)
    if not db_device:
        return None
    
    if device_update.name is not None:
        db_device.name = device_update.name
    
    if device_update.position_x is not None:
        db_device.position_x = device_update.position_x
    
    if device_update.position_y is not None:
        db_device.position_y = device_update.position_y

    if device_update.room_id is not None:
        db_device.room_id = device_update.room_id
    
    db.commit()
    db.refresh(db_device)
    return db_device


def update_device_state(
    db: Session,
    device_id: UUID,
    new_state: dict[str, Any],
    triggered_by: Optional[UUID] = None,
    action="state_changed"
) -> Optional[Device]:
    """
    Update device state and log history
    
    Args:
        db: Database session
        device_id: Device UUID
        new_state: New device state
        triggered_by: User UUID who triggered (None for automation)
        
    Returns:
        Updated device or None if not found
    """
    db_device = get_device_by_id(db, device_id)
    if not db_device:
        return None
    
    # Save old state for history
    old_state = db_device.state.copy() if db_device.state else {}
    
    # Update state
    db_device.state = new_state
    db_device.updated_at = datetime.now(timezone.utc)
    
    # Log history
    create_device_history(
        db=db,
        device_id=device_id,
        action=action,
        old_state=old_state,
        new_state=new_state,
        triggered_by=triggered_by
    )
    
    db.commit()
    db.refresh(db_device)
    return db_device


# ============================================
# DEVICE - DELETE
# ============================================

def delete_device(db: Session, device_id: UUID) -> bool:
    """Delete device"""
    db_device = get_device_by_id(db, device_id)
    if not db_device:
        return False
    
    db.delete(db_device)
    db.commit()
    return True


# ============================================
# DEVICE HISTORY
# ============================================

def create_device_history(
    db: Session,
    device_id: UUID,
    action: str,
    old_state: Optional[dict] = None,
    new_state: Optional[dict] = None,
    triggered_by: Optional[UUID] = None
) -> DeviceHistory:
    """Create device history entry"""
    db_history = DeviceHistory(
        device_id=device_id,
        action=action,
        old_state=old_state,
        new_state=new_state,
        triggered_by=triggered_by
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history


def get_device_history(
    db: Session,
    device_id: UUID,
    skip: int = 0,
    limit: int = 50
) -> tuple[list[DeviceHistory], int]:
    """
    Get device history paginated
    
    Returns:
        Tuple of (history list, total count)
    """
    query = db.query(DeviceHistory).filter(DeviceHistory.device_id == device_id)
    
    total = query.count()
    history = query.order_by(DeviceHistory.created_at.desc()).offset(skip).limit(limit).all()
    
    return history, total


def cleanup_old_history(db: Session, days: int = 7) -> int:
    """
    Delete device history older than specified days
    
    Args:
        db: Database session
        days: Number of days to keep
        
    Returns:
        Number of deleted records
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    deleted = db.query(DeviceHistory).filter(
        DeviceHistory.created_at < threshold
    ).delete()
    
    db.commit()
    return deleted


# ============================================
# SENSOR DATA
# ============================================

def create_sensor_data(
    db: Session,
    device_id: UUID,
    data: dict[str, Any],
    is_downsampled: bool = False
) -> SensorData:
    """Create sensor data entry"""
    db_data = SensorData(
        device_id=device_id,
        data=data,
        is_downsampled=is_downsampled
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data


def get_sensor_data(
    db: Session,
    device_id: UUID,
    skip: int = 0,
    limit: int = 100,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> tuple[list[SensorData], int]:
    """
    Get sensor data paginated with optional time range
    
    Returns:
        Tuple of (sensor data list, total count)
    """
    query = db.query(SensorData).filter(SensorData.device_id == device_id)
    
    # Apply time range filters
    if start_time:
        query = query.filter(SensorData.created_at >= start_time)
    
    if end_time:
        query = query.filter(SensorData.created_at <= end_time)
    
    total = query.count()
    data = query.order_by(SensorData.created_at.desc()).offset(skip).limit(limit).all()
    
    return data, total


def get_latest_sensor_data(db: Session, device_id: UUID) -> Optional[SensorData]:
    """Get latest sensor reading"""
    return db.query(SensorData).filter(
        SensorData.device_id == device_id
    ).order_by(SensorData.created_at.desc()).first()


def cleanup_old_sensor_data(db: Session, days: int = 7) -> int:
    """
    Delete sensor data older than specified days
    
    Args:
        db: Database session
        days: Number of days to keep
        
    Returns:
        Number of deleted records
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    deleted = db.query(SensorData).filter(
        SensorData.created_at < threshold
    ).delete()
    
    db.commit()
    return deleted


# ============================================
# STATISTICS
# ============================================

def count_devices(db: Session) -> int:
    """Get total number of devices"""
    return db.query(func.count(Device.id)).scalar()


def count_home_devices(db: Session, home_id: UUID) -> int:
    """Get number of devices in a home"""
    from app.models.board_model import Board
    
    return db.query(func.count(Device.id)).join(Board).filter(
        Board.home_id == home_id
    ).scalar()


def count_board_devices(db: Session, board_id: UUID) -> int:
    """Get number of devices on a board"""
    return db.query(func.count(Device.id)).filter(
        Device.board_id == board_id
    ).scalar()