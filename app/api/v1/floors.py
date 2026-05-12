"""
Floors API Endpoints
Floor and room management
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.crud import home_crud as crud_home
from app.schemas.home_schemas import (
    FloorCreate,
    FloorResponse,
    RoomCreate,
    RoomUpdate,
    RoomResponse
)

router = APIRouter(tags=["Floors & Rooms"])


# ============================================
# FLOORS
# ============================================

@router.post("/homes/{home_id}/floors", response_model=FloorResponse, status_code=status.HTTP_201_CREATED)
async def create_floor(
    home_id: UUID,
    floor_data: FloorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create floor in home
    
    - Only owner can create floors
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can create floors"
        )
    
    floor = crud_home.create_floor(db, home_id, floor_data)
    
    # Add rooms count
    rooms = crud_home.get_floor_rooms(db, floor.id)
    floor.rooms_count = len(rooms)
    
    return floor


@router.get("/homes/{home_id}/floors", response_model=list[FloorResponse])
async def list_floors(
    home_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all floors in home
    
    - User must be a member
    """
    # Check if user is member
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    floors = crud_home.get_home_floors(db, home_id)
    
    # Add rooms count for each floor
    for floor in floors:
        rooms = crud_home.get_floor_rooms(db, floor.id)
        floor.rooms_count = len(rooms)
    
    return floors


@router.delete("/floors/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_floor(
    floor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete floor
    
    - Only owner can delete floors
    - Cascade deletes all rooms on floor
    """
    # Get floor to check home ownership
    floor = crud_home.get_floor_by_id(db, floor_id)
    
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floor not found"
        )
    
    # Check if user is owner of the home
    if not crud_home.is_home_owner(db, floor.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete floors"
        )
    
    crud_home.delete_floor(db, floor_id)
    
    return None


# ============================================
# ROOMS
# ============================================

@router.post("/floors/{floor_id}/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    floor_id: UUID,
    room_data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create room on floor
    
    - Only owner can create rooms
    """
    # Get floor to check home ownership
    floor = crud_home.get_floor_by_id(db, floor_id)
    
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floor not found"
        )
    
    # Check if user is owner of the home
    if not crud_home.is_home_owner(db, floor.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can create rooms"
        )
    
    room = crud_home.create_room(db, floor_id, room_data)
    
    # Add devices count
    from app.crud import device_crud as crud_device
    room.devices_count = 0  # Initially no devices
    
    return room


@router.get("/floors/{floor_id}/rooms", response_model=list[RoomResponse])
async def list_rooms(
    floor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all rooms on floor
    
    - User must be a member of home
    """
    # Get floor to check home membership
    floor = crud_home.get_floor_by_id(db, floor_id)
    
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floor not found"
        )
    
    # Check if user is member
    if not crud_home.is_home_member(db, floor.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    rooms = crud_home.get_floor_rooms(db, floor_id)
    
    # Add devices count for each room
    from app.models.device_model import Device
    
    for room in rooms:
        devices_count = db.query(Device).filter(
            Device.room_id == room.id
        ).count()
        room.devices_count = devices_count
    
    return rooms


@router.put("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: UUID,
    room_update: RoomUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update room
    
    - Only owner can update rooms
    """
    # Get room to check home ownership
    room = crud_home.get_room_by_id(db, room_id)
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    
    floor = crud_home.get_floor_by_id(db, room.floor_id)
    
    # Check if user is owner of the home
    if not crud_home.is_home_owner(db, floor.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can update rooms"
        )
    
    room = crud_home.update_room(db, room_id, room_update)
    
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete room
    
    - Only owner can delete rooms
    - Boards in room will have room_id set to NULL
    """
    # Get room to check home ownership
    room = crud_home.get_room_by_id(db, room_id)
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    
    floor = crud_home.get_floor_by_id(db, room.floor_id)
    
    # Check if user is owner of the home
    if not crud_home.is_home_owner(db, floor.home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete rooms"
        )
    
    crud_home.delete_room(db, room_id)
    
    return None