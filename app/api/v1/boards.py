"""
Boards API Endpoints
Board pairing and management
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.crud import home as crud_home
from app.crud import board as crud_board
from app.schemas.board import (
    BoardPair,
    BoardPairResponse,
    BoardUpdate,
    BoardResponse,
    BoardDetailResponse,
    BoardListResponse
)
from app.services.board_service import create_devices_for_board

router = APIRouter(prefix="/boards", tags=["Boards"])


# ============================================
# PAIR BOARD
# ============================================

@router.post("/pair", response_model=BoardPairResponse, status_code=status.HTTP_201_CREATED)
async def pair_board(
    pair_data: BoardPair,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Pair board to home
    
    - Board must exist (registered by firmware)
    - User must be owner of home
    - Auto-creates devices based on board template
    """
    # Check if user is owner of home
    if not crud_home.is_home_owner(db, pair_data.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can pair boards"
        )
    
    # Check if board exists
    board = crud_board.get_board_by_mac(db, pair_data.mac_address)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Board with MAC {pair_data.mac_address} not found. Board must connect first."
        )
    
    # Check if already paired
    if board.home_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board is already paired to a home"
        )
    
    # Pair board
    board = crud_board.pair_board(db, pair_data.mac_address, pair_data.home_id)
    
    # Create devices from template
    devices = create_devices_for_board(db, board)
    
    return BoardPairResponse(
        board=board,
        devices=devices
    )


# ============================================
# LIST BOARDS
# ============================================

@router.get("", response_model=BoardListResponse)
async def list_my_boards(
    home_id: UUID = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's boards
    
    - If home_id provided, returns boards in that home
    - Otherwise returns boards in all user's homes
    """
    if home_id:
        # Check if user is member of home
        if not crud_home.is_home_member(db, home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this home"
            )
        
        boards = crud_board.get_home_boards(db, home_id)
    else:
        # Get boards from all user's homes
        user_homes = crud_home.get_user_homes(db, current_user.id)
        boards = []
        
        for home, role in user_homes:
            home_boards = crud_board.get_home_boards(db, home.id)
            boards.extend(home_boards)
    
    # Convert to detail response
    board_details = []
    from app.crud import device as crud_device
    
    for board in boards:
        devices_count = crud_device.count_board_devices(db, board.id)
        
        detail = BoardDetailResponse(
            id=board.id,
            mac_address=board.mac_address,
            board_type=board.board_type,
            name=board.name,
            firmware_version=board.firmware_version,
            status=board.status.value,
            last_seen=board.last_seen,
            paired_at=board.paired_at,
            created_at=board.created_at,
            home_id=board.home_id,
            room_id=board.room_id,
            devices_count=devices_count
        )
        
        board_details.append(detail)
    
    return BoardListResponse(
        items=board_details,
        total=len(board_details)
    )


# ============================================
# GET BOARD
# ============================================

@router.get("/{board_id}", response_model=BoardDetailResponse)
async def get_board(
    board_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get board details"""
    board = crud_board.get_board_by_id(db, board_id)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if user has access to this board
    if board.home_id:
        if not crud_home.is_home_member(db, board.home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this board"
            )
    
    # Get devices count
    from app.crud import device as crud_device
    devices_count = crud_device.count_board_devices(db, board.id)
    
    return BoardDetailResponse(
        id=board.id,
        mac_address=board.mac_address,
        board_type=board.board_type,
        name=board.name,
        firmware_version=board.firmware_version,
        status=board.status.value,
        last_seen=board.last_seen,
        paired_at=board.paired_at,
        created_at=board.created_at,
        home_id=board.home_id,
        room_id=board.room_id,
        devices_count=devices_count,
        room=board.room
    )


# ============================================
# UPDATE BOARD
# ============================================

@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: UUID,
    board_update: BoardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update board information
    
    - Only owner can update board
    """
    board = crud_board.get_board_by_id(db, board_id)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if user is owner of the home
    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can update boards"
        )
    
    board = crud_board.update_board(db, board_id, board_update)
    
    return board


# ============================================
# UNPAIR BOARD
# ============================================

@router.post("/{board_id}/unpair", response_model=BoardResponse)
async def unpair_board(
    board_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unpair board from home
    
    - Only owner can unpair boards
    - Removes board from home but keeps in database
    """
    board = crud_board.get_board_by_id(db, board_id)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    if not board.home_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board is not paired to any home"
        )
    
    # Check if user is owner of the home
    if not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can unpair boards"
        )
    
    board = crud_board.unpair_board(db, board_id)
    
    return board


# ============================================
# DELETE BOARD
# ============================================

@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete board
    
    - Only owner can delete boards
    - Cascade deletes all devices
    """
    board = crud_board.get_board_by_id(db, board_id)
    
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found"
        )
    
    # Check if user is owner of the home
    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete boards"
        )
    
    crud_board.delete_board(db, board_id)
    
    return None