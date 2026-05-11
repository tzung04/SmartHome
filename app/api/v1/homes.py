"""
Homes API Endpoints
Home management (create, read, update, delete)
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.crud import home_crud as crud_home
from app.schemas.home_schemas import (
    HomeCreate,
    HomeUpdate,
    HomeResponse,
    HomeDetailResponse,
    HomeListResponse
)

router = APIRouter(prefix="/homes", tags=["Homes"])


# ============================================
# CREATE HOME
# ============================================

@router.post("", response_model=HomeResponse, status_code=status.HTTP_201_CREATED)
async def create_home(
    home_data: HomeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new home
    
    - User becomes owner automatically
    - Owner membership created automatically
    """
    home = crud_home.create_home(
        db,
        home_data,
        owner_id=current_user.id
    )
    
    return home


# ============================================
# LIST HOMES
# ============================================

@router.get("", response_model=HomeListResponse)
async def list_my_homes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all homes where user is a member
    
    Returns homes with user's role (owner/member)
    """
    homes_with_roles = crud_home.get_user_homes(db, current_user.id)
    
    # Convert to HomeWithRole schema
    from app.schemas.home_schemas import HomeWithRole
    
    items = []
    for home, role in homes_with_roles:
        items.append(HomeWithRole(
            id=home.id,
            name=home.name,
            address=home.address,
            role=role.value,
            created_at=home.created_at
        ))
    
    return HomeListResponse(
        items=items,
        total=len(items)
    )


# ============================================
# GET HOME
# ============================================

@router.get("/{home_id}", response_model=HomeDetailResponse)
async def get_home(
    home_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get home details
    
    - User must be a member of the home
    - Returns home with member/board counts
    """
    # Check if user is member
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    home = crud_home.get_home_by_id(db, home_id)
    
    if not home:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Home not found"
        )
    
    # Get counts
    members_count = crud_home.count_home_members(db, home_id)
    
    from app.crud import board_crud as crud_board
    boards_count = crud_board.count_home_boards(db, home_id)
    
    # Build response
    return HomeDetailResponse(
        id=home.id,
        name=home.name,
        address=home.address,
        owner_id=home.owner_id,
        created_at=home.created_at,
        updated_at=home.updated_at,
        members_count=members_count,
        boards_count=boards_count,
        owner=home.owner
    )


# ============================================
# UPDATE HOME
# ============================================

@router.put("/{home_id}", response_model=HomeResponse)
async def update_home(
    home_id: UUID,
    home_update: HomeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update home information
    
    - Only owner can update home
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can update home"
        )
    
    home = crud_home.update_home(db, home_id, home_update)
    
    if not home:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Home not found"
        )
    
    return home


# ============================================
# DELETE HOME
# ============================================

@router.delete("/{home_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_home(
    home_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete home
    
    - Only owner can delete home
    - Cascade deletes all floors, rooms, boards, devices
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can delete home"
        )
    
    success = crud_home.delete_home(db, home_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Home not found"
        )
    
    return None