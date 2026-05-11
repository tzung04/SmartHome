"""
Admin API Endpoints
Firmware management and system statistics (Super Admin only)
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_super_admin
from app.models.user_model import User
from app.models.firmware_model import Firmware
from app.crud import user_crud as crud_user
from app.crud import board_crud as crud_board
from app.crud import device_crud as crud_device
from app.schemas.firmware_schemas import (
    FirmwareResponse,
    FirmwareDetailResponse,
    FirmwareListResponse,
    FirmwareDeleteResponse
)
from app.schemas.board_schemas import BoardOTARequest, BoardOTAResponse
from app.schemas.user_schemas import UserListResponse, UserBanRequest, UserBanResponse
from app.services.storage_service import upload_firmware, delete_firmware
from app.services.mqtt_service import publish_ota_update

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============================================
# FIRMWARE MANAGEMENT
# ============================================

@router.post("/firmware/upload", response_model=FirmwareResponse)
async def upload_firmware_file(
    file: UploadFile = File(...),
    board_type: str = Form(...),
    version: str = Form(...),
    changelog: Optional[str] = Form(None),
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Upload firmware file (Super Admin only)
    
    - Uploads to Supabase Storage
    - Calculates MD5 hash
    - Creates firmware record
    """
    # Validate file extension
    if not file.filename.endswith('.bin'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firmware file must be .bin format"
        )
    
    # Read file
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    # Calculate MD5
    import hashlib
    md5_hash = hashlib.md5(file_bytes).hexdigest()
    
    # Check if version already exists
    existing = db.query(Firmware).filter(
        Firmware.board_type == board_type,
        Firmware.version == version
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Firmware {board_type} v{version} already exists"
        )
    
    # Upload to storage
    file_url = upload_firmware(board_type, version, file_bytes)
    
    if not file_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload firmware to storage"
        )
    
    # Create firmware record
    firmware = Firmware(
        board_type=board_type,
        version=version,
        file_url=file_url,
        file_size_bytes=file_size,
        md5_hash=md5_hash,
        changelog=changelog,
        uploaded_by=admin.id
    )
    
    db.add(firmware)
    db.commit()
    db.refresh(firmware)
    
    return firmware


@router.get("/firmware", response_model=FirmwareListResponse)
async def list_firmwares(
    board_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    List all firmwares (Super Admin only)
    
    Optional filters: board_type, is_active
    """
    query = db.query(Firmware)
    
    if board_type:
        query = query.filter(Firmware.board_type == board_type)
    
    if is_active is not None:
        query = query.filter(Firmware.is_active == is_active)
    
    firmwares = query.order_by(Firmware.uploaded_at.desc()).all()
    
    return FirmwareListResponse(
        items=firmwares,
        total=len(firmwares)
    )


@router.get("/firmware/{firmware_id}", response_model=FirmwareDetailResponse)
async def get_firmware(
    firmware_id: UUID,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Get firmware details (Super Admin only)"""
    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firmware not found"
        )
    
    return firmware


@router.delete("/firmware/{firmware_id}", response_model=FirmwareDeleteResponse)
async def delete_firmware_file(
    firmware_id: UUID,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Delete firmware (Super Admin only)
    
    Deletes from storage and database
    """
    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firmware not found"
        )
    
    # Delete from storage
    delete_firmware(firmware.board_type, firmware.version)
    
    # Delete from database
    db.delete(firmware)
    db.commit()
    
    return FirmwareDeleteResponse(firmware_id=firmware_id)


# ============================================
# OTA UPDATE
# ============================================

@router.post("/boards/{board_id}/ota", response_model=BoardOTAResponse)
async def trigger_ota_update(
    board_id: UUID,
    request: BoardOTARequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Trigger OTA firmware update for board (Super Admin only)
    
    Sends update command via MQTT
    """
    # Get board
    board = crud_board.get_board_by_id(db, board_id)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Get firmware
    firmware = db.query(Firmware).filter(Firmware.id == request.firmware_id).first()
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firmware not found"
        )
    
    # Validate board type matches firmware
    if board.board_type != firmware.board_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Firmware type mismatch. Board is {board.board_type}, firmware is {firmware.board_type}"
        )
    
    # Check if board is online
    if board.status != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board is {board.status}. OTA requires board to be online"
        )
    
    # Publish OTA command via MQTT
    success = publish_ota_update(
        board.mac_address,
        firmware.file_url,
        firmware.md5_hash,
        firmware.version
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTA command via MQTT"
        )
    
    return BoardOTAResponse(
        board_id=board_id,
        target_version=firmware.version
    )


# ============================================
# USER MANAGEMENT
# ============================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    limit: int = 50,
    is_active: Optional[bool] = None,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (Super Admin only)
    
    Pagination and filters supported
    """
    skip = (page - 1) * limit
    
    users, total = crud_user.get_users(
        db,
        skip=skip,
        limit=limit,
        is_active=is_active
    )
    
    pages = (total + limit - 1) // limit
    
    return UserListResponse(
        items=users,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


@router.put("/users/{user_id}/ban", response_model=UserBanResponse)
async def ban_user(
    user_id: UUID,
    request: UserBanRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Ban user (Super Admin only)
    
    Sets is_active = False
    """
    user = crud_user.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Cannot ban super admin
    if user.role == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot ban super admin"
        )
    
    # Ban user
    crud_user.ban_user(db, user_id)
    
    return UserBanResponse(
        user_id=user_id,
        is_active=False
    )


@router.put("/users/{user_id}/unban", response_model=UserBanResponse)
async def unban_user(
    user_id: UUID,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Unban user (Super Admin only)"""
    user = crud_user.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    crud_user.unban_user(db, user_id)
    
    return UserBanResponse(
        user_id=user_id,
        is_active=True,
        message="User account activated"
    )


# ============================================
# SYSTEM STATISTICS
# ============================================

@router.get("/stats")
async def get_system_stats(
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get system statistics (Super Admin only)
    
    Returns counts for users, homes, boards, devices
    """
    from app.crud import home_crud as crud_home
    
    stats = {
        "users": {
            "total": crud_user.count_users(db),
            "active": crud_user.count_active_users(db),
            "super_admins": crud_user.count_super_admins(db)
        },
        "homes": {
            "total": crud_home.count_homes(db)
        },
        "boards": {
            "total": crud_board.count_boards(db),
            "online": crud_board.count_online_boards(db)
        },
        "devices": {
            "total": crud_device.count_devices(db)
        }
    }
    
    return stats