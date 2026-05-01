"""
Sensors API Endpoints
Sensor data queries and statistics
"""
from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.crud import home as crud_home
from app.crud import device as crud_device
from app.schemas.device import (
    SensorDataResponse,
    SensorDataLatest
)

router = APIRouter(prefix="/sensors", tags=["Sensors"])


# ============================================
# GET SENSOR DATA
# ============================================

@router.get("/{device_id}/data", response_model=SensorDataResponse)
async def get_sensor_data(
    device_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get sensor data history
    
    - Paginated sensor readings
    - Optional time range filter
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check if device is a sensor
    sensor_types = ["dht11", "pir", "ldr"]
    if device.device_type.value not in sensor_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is not a sensor. Type: {device.device_type.value}"
        )
    
    board = device.board
    
    # Check access
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this device"
        )
    
    skip = (page - 1) * limit
    
    data, total = crud_device.get_sensor_data(
        db,
        device_id,
        skip=skip,
        limit=limit,
        start_time=start_time,
        end_time=end_time
    )
    
    pages = (total + limit - 1) // limit
    
    return SensorDataResponse(
        items=data,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


# ============================================
# GET LATEST SENSOR DATA
# ============================================

@router.get("/{device_id}/latest", response_model=SensorDataLatest)
async def get_latest_sensor_data(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get latest sensor reading
    
    - Returns most recent data point
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check if device is a sensor
    sensor_types = ["dht11", "pir", "ldr"]
    if device.device_type.value not in sensor_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is not a sensor. Type: {device.device_type.value}"
        )
    
    board = device.board
    
    # Check access
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this device"
        )
    
    latest = crud_device.get_latest_sensor_data(db, device_id)
    
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensor data available"
        )
    
    return SensorDataLatest(
        data=latest.data,
        timestamp=latest.created_at
    )