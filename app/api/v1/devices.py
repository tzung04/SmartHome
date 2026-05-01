"""
Devices API Endpoints
Device control, updates, and history
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.crud import home as crud_home
from app.crud import board as crud_board
from app.crud import device as crud_device
from app.schemas.device import (
    DeviceControl,
    DeviceControlResponse,
    DeviceUpdate,
    DeviceResponse,
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceHistoryResponse
)
from app.services.mqtt_service import publish_device_control
from app.services.websocket_manager import notify_device_state_change

router = APIRouter(prefix="/devices", tags=["Devices"])


# ============================================
# LIST DEVICES
# ============================================

@router.get("", response_model=DeviceListResponse)
async def list_devices(
    board_id: UUID = None,
    home_id: UUID = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get devices
    
    - Filter by board_id or home_id
    """
    if board_id:
        # Get board and check access
        board = crud_board.get_board_by_id(db, board_id)
        
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found"
            )
        
        if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this board"
            )
        
        devices = crud_device.get_board_devices(db, board_id)
    
    elif home_id:
        # Check if user is member
        if not crud_home.is_home_member(db, home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this home"
            )
        
        devices = crud_device.get_home_devices(db, home_id)
    
    else:
        # Get all devices from user's homes
        user_homes = crud_home.get_user_homes(db, current_user.id)
        devices = []
        
        for home, role in user_homes:
            home_devices = crud_device.get_home_devices(db, home.id)
            devices.extend(home_devices)
    
    # Convert to detail response
    device_details = [
        DeviceDetailResponse(
            id=d.id,
            board_id=d.board_id,
            device_type=d.device_type.value,
            name=d.name,
            gpio=d.gpio,
            state=d.state,
            position_x=d.position_x,
            position_y=d.position_y,
            created_at=d.created_at,
            updated_at=d.updated_at,
            board=d.board
        )
        for d in devices
    ]
    
    return DeviceListResponse(
        items=device_details,
        total=len(device_details)
    )


# ============================================
# GET DEVICE
# ============================================

@router.get("/{device_id}", response_model=DeviceDetailResponse)
async def get_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get device details"""
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check access via board's home
    board = device.board
    if board and board.home_id:
        if not crud_home.is_home_member(db, board.home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this device"
            )
    
    return DeviceDetailResponse(
        id=device.id,
        board_id=device.board_id,
        device_type=device.device_type.value,
        name=device.name,
        gpio=device.gpio,
        state=device.state,
        position_x=device.position_x,
        position_y=device.position_y,
        created_at=device.created_at,
        updated_at=device.updated_at,
        board=board
    )


# ============================================
# CONTROL DEVICE
# ============================================

@router.post("/{device_id}/control", response_model=DeviceControlResponse)
async def control_device(
    device_id: UUID,
    control: DeviceControl,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Control device
    
    - Sends command via MQTT
    - Updates device state
    - Creates history entry
    - Notifies WebSocket clients
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    board = device.board
    
    # Check access
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this device"
        )
    
    # Check if board is online
    if board.status != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board is {board.status}. Device control requires board to be online"
        )
    
    # Send command via MQTT
    success = publish_device_control(
        board.mac_address,
        device.gpio,
        control.state
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send command via MQTT"
        )
    
    # Update device state
    device = crud_device.update_device_state(
        db,
        device_id,
        control.state,
        triggered_by=current_user.id
    )
    
    # Notify WebSocket clients
    if board.home_id:
        await notify_device_state_change(
            board.home_id,
            device_id,
            control.state
        )
    
    from datetime import datetime, timezone
    
    return DeviceControlResponse(
        device_id=device_id,
        state=control.state,
        timestamp=datetime.now(timezone.utc)
    )


# ============================================
# UPDATE DEVICE
# ============================================

@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_update: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update device information (name, position)
    
    - Only owner can update devices
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    board = device.board
    
    # Check if user is owner
    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can update devices"
        )
    
    device = crud_device.update_device(db, device_id, device_update)
    
    return device


# ============================================
# DEVICE HISTORY
# ============================================

@router.get("/{device_id}/history", response_model=DeviceHistoryResponse)
async def get_device_history(
    device_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get device history
    
    - Paginated list of state changes
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    board = device.board
    
    # Check access
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this device"
        )
    
    skip = (page - 1) * limit
    
    history, total = crud_device.get_device_history(db, device_id, skip, limit)
    
    pages = (total + limit - 1) // limit
    
    return DeviceHistoryResponse(
        items=history,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )