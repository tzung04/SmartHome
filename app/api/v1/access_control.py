"""
Access Control API Endpoints
RFID card management and access logs
"""
from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.models.access_control_model import AccessResult
from app.crud import home_crud as crud_home
from app.crud import board_crud as crud_board
from app.crud import access_control_crud as crud_access
from app.schemas.access_control_schemas import (
    CardCreate,
    CardUpdate,
    CardResponse,
    CardListResponse,
    CardDeactivateResponse,
    CardLearnRequest,
    CardLearnResponse,
    AccessLogListResponse
)
from app.services.mqtt_service import mqtt_service
from app.services.storage_service import upload_access_log_image
from app.services.websocket_manager import manager as ws_manager


import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Access Control"])


# Helper
def _sync_cards_to_home(db, home_id: UUID) -> None:
    """Sync active cards tới tất cả ESP32_ACCESS_V1 boards online trong home"""
    boards = crud_board.get_home_boards_by_type(db, home_id, "ESP32_ACCESS_V1")
    if not boards:
        return

    active_cards = crud_access.get_home_cards(db, home_id, is_active=True)
    cards_payload = [
        {"card_uid": c.card_uid, "owner_name": c.owner_name}
        for c in active_cards
    ]

    for board in boards:
        if board.status == "online":
            mqtt_service.publish_card_sync(board.mac_address, cards_payload)


# ============================================
# CARDS
# ============================================

@router.post("/homes/{home_id}/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    home_id: UUID,
    card_data: CardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create access card

    - Only owner can create cards
    """
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can create cards"
        )

    existing = crud_access.get_card_by_uid(db, card_data.card_uid)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card with this UID already exists"
        )

    card = crud_access.create_access_card(
        db,
        home_id=home_id,
        card_uid=card_data.card_uid,
        owner_name=card_data.owner_name,
        owner_user_id=card_data.owner_user_id,
        valid_until=card_data.valid_until
    )

    _sync_cards_to_home(db, home_id)

    return card


@router.get("/homes/{home_id}/cards", response_model=CardListResponse)
async def list_cards(
    home_id: UUID,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all cards in home"""
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )

    cards = crud_access.get_home_cards(db, home_id, is_active)

    return CardListResponse(
        items=cards,
        total=len(cards)
    )


@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: UUID,
    card_update: CardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update card - Only owner can update cards"""
    card = crud_access.get_card_by_id(db, card_id)

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    if not crud_home.is_home_owner(db, card.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can update cards"
        )

    card = crud_access.update_card(
        db,
        card_id,
        owner_name=card_update.owner_name,
        valid_until=card_update.valid_until
    )

    return card


@router.post("/cards/{card_id}/deactivate", response_model=CardDeactivateResponse)
async def deactivate_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate card - Only owner can deactivate cards"""
    card = crud_access.get_card_by_id(db, card_id)

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    if not crud_home.is_home_owner(db, card.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can deactivate cards"
        )

    card = crud_access.deactivate_card(db, card_id)

    _sync_cards_to_home(db, card.home_id)

    return CardDeactivateResponse(
        card_id=card_id,
        is_active=False
    )


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete card - Only owner can delete cards"""
    card = crud_access.get_card_by_id(db, card_id)

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    if not crud_home.is_home_owner(db, card.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete cards"
        )

    home_id = card.home_id
    crud_access.delete_card(db, card_id)

    _sync_cards_to_home(db, home_id)

    return None


# ============================================
# CARD LEARNING
# ============================================

@router.post("/boards/{board_id}/learn", response_model=CardLearnResponse)
async def trigger_card_learning(
    board_id: UUID,
    request: CardLearnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger card learning mode on board"""
    board = crud_board.get_board_by_id(db, board_id)

    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )

    if board.board_type != "ESP32_ACCESS_V1":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board does not support RFID"
        )

    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can trigger card learning"
        )

    if board.status != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board is {board.status}. Learning requires board to be online"
        )

    success = mqtt_service.publish_card_learn(
        board.mac_address,
        timeout=request.timeout
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send learning command via MQTT"
        )

    return CardLearnResponse(
        board_id=board_id,
        timeout=request.timeout
    )


# ============================================
# ACCESS LOG IMAGE UPLOAD (từ ESP32-CAM qua HTTP)
# ============================================

@router.post("/boards/access/image", status_code=status.HTTP_200_OK)
async def upload_access_image(
    request_id: str = Form(..., description="UUID do ESP32 sinh, khớp với MQTT event"),
    image: UploadFile = File(..., description="Ảnh JPEG từ ESP32-CAM"),
    x_board_mac: str = Header(..., alias="X-Board-Mac", description="MAC address của board"),
    db: Session = Depends(get_db)
):
    """
    Nhận ảnh từ ESP32-CAM sau khi access event.
    """
    board = crud_board.get_board_by_mac(db, x_board_mac)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )

    if board.board_type != "ESP32_ACCESS_V1":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board does not support access image upload"
        )

    # Board phải đã được pair vào một home
    if not board.home_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Board is not paired to any home"
        )

    access_log = crud_access.get_log_by_request_id(db, request_id)
    if not access_log:
        logger.warning(
            f"Image upload received but no access_log found: "
            f"board={x_board_mac}, request_id={request_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access log not found for this request_id. MQTT event may not have arrived yet."
        )

    if access_log.image_url:
        logger.warning(f"Duplicate image upload for request_id={request_id}, ignored")
        return {"message": "Image already uploaded", "image_url": access_log.image_url}

    if image.content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG images are accepted"
        )

    image_bytes = await image.read()

    max_size = 2 * 1024 * 1024
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large. Maximum size is 2MB"
        )

    image_url = upload_access_log_image(x_board_mac, image_bytes)
    if not image_url:
        logger.error(f"Supabase upload failed: board={x_board_mac}, request_id={request_id}")
        return {"status": "success", "warning": "image_upload_failed"}

    updated_log = crud_access.update_log_image_url(db, request_id, image_url)
    if not updated_log:
        logger.error(f"Failed to update access_log image_url: request_id={request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update access log"
        )

    logger.info(
        f"Access image uploaded: board={x_board_mac}, "
        f"request_id={request_id}, url={image_url}"
    )

    if board.home_id:
        await ws_manager.notify_access_log_image_ready(
            home_id=board.home_id,
            log_id=updated_log.id,
            request_id=request_id,
            image_url=image_url
        )

    return {
        "message": "Image uploaded successfully",
        "log_id": str(updated_log.id),
        "image_url": image_url
    }


# ============================================
# ACCESS LOGS
# ============================================

@router.get("/homes/{home_id}/access-logs", response_model=AccessLogListResponse)
async def list_access_logs(
    home_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    result: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get access logs for home - paginated with filters"""
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )

    skip = (page - 1) * limit

    access_result = AccessResult(result) if result else None

    logs, total = crud_access.get_home_logs(
        db,
        home_id,
        skip=skip,
        limit=limit,
        result=access_result,
        start_time=start_time,
        end_time=end_time
    )

    pages = (total + limit - 1) // limit

    return AccessLogListResponse(
        items=logs,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


@router.get("/homes/{home_id}/access-stats")
async def get_access_stats(
    home_id: UUID,
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get access statistics for home"""
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )

    stats = crud_access.get_access_stats(db, home_id, days)

    return stats