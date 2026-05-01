"""
Access Control API Endpoints
RFID card management and access logs
"""
from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.models.access_control import AccessResult
from app.crud import home as crud_home
from app.crud import board as crud_board
from app.crud import access_control as crud_access
from app.schemas.access_control import (
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

router = APIRouter(tags=["Access Control"])


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
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can create cards"
        )
    
    # Check if card UID already exists
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
    
    # TODO: Sync cards to all ESP32-CAM boards in this home
    
    return card


@router.get("/homes/{home_id}/cards", response_model=CardListResponse)
async def list_cards(
    home_id: UUID,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all cards in home
    
    - User must be a member
    """
    # Check if user is member
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
    """
    Update card
    
    - Only owner can update cards
    """
    card = crud_access.get_card_by_id(db, card_id)
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if user is owner of home
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
    """
    Deactivate card
    
    - Only owner can deactivate cards
    """
    card = crud_access.get_card_by_id(db, card_id)
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if user is owner of home
    if not crud_home.is_home_owner(db, card.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can deactivate cards"
        )
    
    card = crud_access.deactivate_card(db, card_id)
    
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
    """
    Delete card
    
    - Only owner can delete cards
    """
    card = crud_access.get_card_by_id(db, card_id)
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Check if user is owner of home
    if not crud_home.is_home_owner(db, card.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete cards"
        )
    
    crud_access.delete_card(db, card_id)
    
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
    """
    Trigger card learning mode on board
    
    - Only owner can trigger learning
    - Board enters learning mode for specified timeout
    """
    board = crud_board.get_board_by_id(db, board_id)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if board is ESP32-CAM (has RFID)
    if board.board_type != "ESP32_ACCESS_V1":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board does not support RFID"
        )
    
    # Check if user is owner
    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can trigger card learning"
        )
    
    # Check if board is online
    if board.status != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Board is {board.status}. Learning requires board to be online"
        )
    
    # Send MQTT command
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
    """
    Get access logs for home
    
    - Paginated with filters
    """
    # Check if user is member
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
    """
    Get access statistics for home
    
    - Count of granted/denied/unknown access attempts
    """
    # Check if user is member
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    stats = crud_access.get_access_stats(db, home_id, days)
    
    return stats