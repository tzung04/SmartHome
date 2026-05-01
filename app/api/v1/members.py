"""
Members API Endpoints
Home member management (invite, remove, transfer ownership)
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.user import User
from app.models.home import MemberRole
from app.crud import home as crud_home
from app.crud import user as crud_user
from app.schemas.home import (
    MemberInvite,
    MemberResponse,
    MemberListResponse,
    MemberUpdateRole,
    MemberRemoveResponse,
    LeaveHomeResponse
)

router = APIRouter(prefix="/homes/{home_id}/members", tags=["Members"])


# ============================================
# LIST MEMBERS
# ============================================

@router.get("", response_model=MemberListResponse)
async def list_members(
    home_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all members of a home
    
    - User must be a member to view
    """
    # Check if user is member
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    members = crud_home.get_home_members(db, home_id)
    
    return MemberListResponse(
        items=members,
        total=len(members)
    )


# ============================================
# INVITE MEMBER
# ============================================

@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    home_id: UUID,
    invite_data: MemberInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invite member to home
    
    - Only owner can invite members
    - User must exist in system
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can invite members"
        )
    
    # Find user by email
    invited_user = crud_user.get_user_by_email(db, invite_data.email)
    
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {invite_data.email} not found"
        )
    
    # Check if already a member
    if crud_home.is_home_member(db, home_id, invited_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this home"
        )
    
    # Add member
    role = MemberRole.OWNER if invite_data.role == "owner" else MemberRole.MEMBER
    
    member = crud_home.create_member(
        db,
        home_id,
        invited_user.id,
        role
    )
    
    return member


# ============================================
# UPDATE MEMBER ROLE (Transfer Ownership)
# ============================================

@router.put("/{user_id}/role", response_model=MemberResponse)
async def update_member_role(
    home_id: UUID,
    user_id: UUID,
    role_update: MemberUpdateRole,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update member role (transfer ownership)
    
    - Only owner can transfer ownership
    - If promoting to owner, current owner becomes member
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can change member roles"
        )
    
    # Cannot change own role
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role. Use transfer ownership instead."
        )
    
    # Check if target user is a member
    if not crud_home.is_home_member(db, home_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this home"
        )
    
    # If promoting to owner, transfer ownership
    if role_update.role == "owner":
        success = crud_home.transfer_ownership(
            db,
            home_id,
            current_owner_id=current_user.id,
            new_owner_id=user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to transfer ownership"
            )
    else:
        # Just update role
        new_role = MemberRole(role_update.role)
        crud_home.update_member_role(db, home_id, user_id, new_role)
    
    # Return updated member
    member = crud_home.get_member(db, home_id, user_id)
    return member


# ============================================
# REMOVE MEMBER
# ============================================

@router.delete("/{user_id}", response_model=MemberRemoveResponse)
async def remove_member(
    home_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove member from home
    
    - Only owner can remove members
    - Cannot remove owner
    """
    # Check if user is owner
    if not crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only home owner can remove members"
        )
    
    # Cannot remove self
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use leave endpoint to leave home"
        )
    
    # Check if target is owner
    if crud_home.is_home_owner(db, home_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove home owner. Transfer ownership first."
        )
    
    success = crud_home.remove_member(db, home_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    return MemberRemoveResponse()


# ============================================
# LEAVE HOME
# ============================================

@router.post("/leave", response_model=LeaveHomeResponse)
async def leave_home(
    home_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Leave home (remove self)
    
    - Owner cannot leave without transferring ownership first
    """
    # Check if user is owner
    if crud_home.is_home_owner(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot leave home. Transfer ownership first."
        )
    
    # Check if user is member
    if not crud_home.is_home_member(db, home_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this home"
        )
    
    success = crud_home.remove_member(db, home_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to leave home"
        )
    
    return LeaveHomeResponse()