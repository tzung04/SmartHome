"""
Timers API Endpoints
Timer scheduling and management
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.crud import home as crud_home
from app.crud import device as crud_device
from app.crud import timer as crud_timer
from app.schemas.timer import (
    TimerCreate,
    TimerResponse,
    TimerDetailResponse,
    TimerListResponse,
    TimerCancelResponse
)

router = APIRouter(prefix="/timers", tags=["Timers"])


# ============================================
# CREATE TIMER
# ============================================

@router.post("", response_model=TimerResponse, status_code=status.HTTP_201_CREATED)
async def create_timer(
    device_id: UUID,
    timer_data: TimerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create timer for device
    
    - Schedule device state change at specific time
    - Execute_at must be in the future
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
    
    # Create timer
    timer = crud_timer.create_timer(
        db,
        device_id=device_id,
        created_by=current_user.id,
        target_state=timer_data.target_state,
        execute_at=timer_data.execute_at
    )
    
    return timer


# ============================================
# LIST TIMERS
# ============================================

@router.get("", response_model=TimerListResponse)
async def list_timers(
    device_id: UUID = None,
    home_id: UUID = None,
    status: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get timers
    
    - Filter by device_id, home_id, or status
    - If no filters, returns user's timers
    """
    from app.models.timer import TimerStatus
    
    if device_id:
        # Get device and check access
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
        
        timer_status = TimerStatus(status) if status else None
        timers = crud_timer.get_device_timers(db, device_id, timer_status)
    
    elif home_id:
        # Check if user is member
        if not crud_home.is_home_member(db, home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this home"
            )
        
        timer_status = TimerStatus(status) if status else None
        timers = crud_timer.get_home_timers(db, home_id, timer_status)
    
    else:
        # Get user's timers
        timer_status = TimerStatus(status) if status else None
        timers = crud_timer.get_user_timers(db, current_user.id, timer_status)
    
    # Convert to detail response
    timer_details = [
        TimerDetailResponse(
            id=t.id,
            device_id=t.device_id,
            created_by=t.created_by,
            target_state=t.target_state,
            execute_at=t.execute_at,
            status=t.status.value,
            retry_count=t.retry_count,
            executed_at=t.executed_at,
            created_at=t.created_at,
            device=t.device
        )
        for t in timers
    ]
    
    return TimerListResponse(
        items=timer_details,
        total=len(timer_details)
    )


# ============================================
# GET TIMER
# ============================================

@router.get("/{timer_id}", response_model=TimerDetailResponse)
async def get_timer(
    timer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get timer details"""
    timer = crud_timer.get_timer_by_id(db, timer_id)
    
    if not timer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timer not found"
        )
    
    # Check access via device's board
    device = timer.device
    board = device.board
    
    if board.home_id and not crud_home.is_home_member(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this timer"
        )
    
    return TimerDetailResponse(
        id=timer.id,
        device_id=timer.device_id,
        created_by=timer.created_by,
        target_state=timer.target_state,
        execute_at=timer.execute_at,
        status=timer.status.value,
        retry_count=timer.retry_count,
        executed_at=timer.executed_at,
        created_at=timer.created_at,
        device=device
    )


# ============================================
# CANCEL TIMER
# ============================================

@router.post("/{timer_id}/cancel", response_model=TimerCancelResponse)
async def cancel_timer(
    timer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel pending timer
    
    - Only pending timers can be cancelled
    """
    timer = crud_timer.get_timer_by_id(db, timer_id)
    
    if not timer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timer not found"
        )
    
    # Check if user created the timer or is owner
    device = timer.device
    board = device.board
    
    is_creator = timer.created_by == current_user.id
    is_owner = board.home_id and crud_home.is_home_owner(db, board.home_id, current_user.id)
    
    if not (is_creator or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only timer creator or home owner can cancel timer"
        )
    
    # Cancel timer
    timer = crud_timer.cancel_timer(db, timer_id)
    
    if not timer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timer cannot be cancelled (already executed/failed/cancelled)"
        )
    
    return TimerCancelResponse(
        timer_id=timer_id,
        status="cancelled"
    )