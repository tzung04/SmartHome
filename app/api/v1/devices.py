"""
Devices API Endpoints
Device control, updates, and history
"""
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.crud import home_crud as crud_home
from app.crud import board_crud as crud_board
from app.crud import device_crud as crud_device
from app.schemas.device_schemas import (
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
        if not crud_home.is_home_member(db, home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this home"
            )
        
        devices = crud_device.get_home_devices(db, home_id)
    
    else:
        user_homes = crud_home.get_user_homes(db, current_user.id)
        devices = []
        for home, role in user_homes:
            home_devices = crud_device.get_home_devices(db, home.id)
            devices.extend(home_devices)
    
    device_details = [
        DeviceDetailResponse(
            id=d.id,
            board_id=d.board_id,
            room_id=d.room_id,
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
        room_id=device.room_id,
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

    Actions:
    - set_state: điều khiển relay/lock bình thường
    - set_auto:  bật/tắt auto mode cho relay trên sensor board
    """
    device = crud_device.get_device_by_id(db, device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    board = device.board
    
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this device"
        )
    
    if board.status != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board is {board.status}. Device control requires board to be online"
        )

    # ── set_state ──────────────────────────────────────────────────────────
    if control.action == "set_state":
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

        new_state = control.state
        history_action = "state_changed"

    # ── set_auto ───────────────────────────────────────────────────────────
    elif control.action == "set_auto":
        # Chỉ relay mới có auto mode
        if device.device_type.value != "relay":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auto mode only supported for relay devices"
            )

        enabled = control.state.get("enabled")
        if enabled is None or not isinstance(enabled, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'enabled' (boolean) is required for set_auto action"
            )

        # Dùng chung topic /control, firmware phân biệt qua action field
        success = publish_device_control(
            board.mac_address,
            device.gpio,
            {
                "action": "set_auto",
                "enabled": enabled
            }
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send command via MQTT"
            )

        # Merge vào state hiện tại — giữ nguyên is_on, chỉ update auto_mode
        current_state = device.state or {}
        new_state = {
            **current_state,
            "auto_mode": {"enabled": enabled}
        }
        history_action = "auto_mode_changed"

    # ── unknown action ─────────────────────────────────────────────────────
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action '{control.action}'. Supported: set_state, set_auto"
        )

    # ── Chung: update DB + WS notify ───────────────────────────────────────
    device = crud_device.update_device_state(
        db,
        device_id,
        new_state,
        triggered_by=current_user.id,
        action=history_action
    )

    if board.home_id:
        await notify_device_state_change(
            board.home_id,
            device_id,
            new_state
        )

    return DeviceControlResponse(
        device_id=device_id,
        state=new_state,
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