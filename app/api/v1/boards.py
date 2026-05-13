"""
Boards API Endpoints
Board pairing and management
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.crud import home_crud as crud_home
from app.crud import board_crud as crud_board
from app.crud import pairing_session_crud as crud_pairing
from app.schemas.board_schemas import (
    BoardPair,
    BoardPairResponse,
    BoardUpdate,
    BoardResponse,
    BoardDetailResponse,
    BoardListResponse
)
from app.services.board_service import create_devices_for_board
from app.services.mqtt_service import publish_paired

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
    Pair board vào home.

    Flow:
      1. Board giữ nút >= 5s → publish MQTT boards/{mac}/pairing
      2. Server tạo pairing_session TTL 30s
      3. User quét QR trên board (chứa MAC) → gọi endpoint này
      4. Server verify session còn hạn → pair → notify board qua MQTT

    Errors:
      - 403: User không phải owner của home
      - 404: Board chưa từng kết nối (không có record trong DB)
      - 408: Board không trong pairing mode hoặc session đã hết hạn (30s)
      - 409: Board đã được pair với home khác
    """
    if not crud_home.is_home_owner(db, pair_data.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can pair boards"
        )

    board = crud_board.get_board_by_mac(db, pair_data.mac_address)
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Board {pair_data.mac_address} chưa từng kết nối. "
                f"Hãy bật board và giữ nút pairing."
            )
        )

    if board.home_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Board đã được pair với một home khác"
        )

    session = crud_pairing.get_active_session(db, pair_data.mac_address)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=(
                "Board không trong pairing mode hoặc phiên pair đã hết hạn (30 giây). "
                "Hãy giữ nút pairing trên board và thử lại."
            )
        )

    board = crud_board.pair_board(db, pair_data.mac_address, pair_data.home_id)

    devices = create_devices_for_board(db, board)

    crud_pairing.delete_session(db, pair_data.mac_address)

    home = crud_home.get_home_by_id(db, pair_data.home_id)
    home_name = home.name if home else "Smart Home"

    publish_paired(
        board_mac=pair_data.mac_address,
        home_id=str(pair_data.home_id),
        home_name=home_name
    )

    return BoardPairResponse(
        board=board,
        devices=devices
    )


# ============================================
# PAIRING STATUS
# ============================================

@router.get("/pairing/{mac_address}")
async def get_pairing_status(
    mac_address: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Kiểm tra board có đang trong pairing mode không.

    App dùng endpoint này sau khi quét QR để kiểm tra
    trước khi hiển thị nút "Pair" cho user.

    Response:
      - is_pairing: true nếu board đang trong pairing mode
      - board_type: loại board (nếu có)
      - seconds_remaining: số giây còn lại của session
    """
    from datetime import datetime, timezone

    session = crud_pairing.get_active_session(db, mac_address)

    if not session:
        return {
            "mac_address": mac_address,
            "is_pairing": False,
            "board_type": None,
            "seconds_remaining": 0
        }

    now = datetime.now(timezone.utc)
    remaining = max(0, int((session.expires_at - now).total_seconds()))

    return {
        "mac_address": mac_address,
        "is_pairing": True,
        "board_type": session.board_type,
        "firmware_version": session.firmware_version,
        "seconds_remaining": remaining
    }


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
        if not crud_home.is_home_member(db, home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this home"
            )
        boards = crud_board.get_home_boards(db, home_id)
    else:
        user_homes = crud_home.get_user_homes(db, current_user.id)
        boards = []
        for home, role in user_homes:
            home_boards = crud_board.get_home_boards(db, home.id)
            boards.extend(home_boards)

    board_details = []
    from app.crud import device_crud as crud_device

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
            devices_count=devices_count
        )
        board_details.append(detail)

    return BoardListResponse(items=board_details, total=len(board_details))


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    if board.home_id:
        if not crud_home.is_home_member(db, board.home_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this board"
            )

    from app.crud import device_crud as crud_device
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
        devices_count=devices_count,
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
    """Update board information — only owner"""
    board = crud_board.get_board_by_id(db, board_id)

    if not board:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

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
    """Unpair board from home — only owner"""
    board = crud_board.get_board_by_id(db, board_id)

    if not board:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    if not board.home_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Board is not paired to any home"
        )

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
    """Delete board — only owner"""
    board = crud_board.get_board_by_id(db, board_id)

    if not board:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    if board.home_id and not crud_home.is_home_owner(db, board.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete boards"
        )

    crud_board.delete_board(db, board_id)
    return None