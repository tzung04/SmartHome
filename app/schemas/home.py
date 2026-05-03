"""
Home Pydantic schemas
Home and member management request/response models
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================
# HOME
# ============================================

class HomeCreate(BaseModel):
    """Create home request"""
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class HomeUpdate(BaseModel):
    """Update home request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)


class HomeResponse(BaseModel):
    """Home response model"""
    id: UUID
    name: str
    address: Optional[str] = None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class HomeDetailResponse(HomeResponse):
    """Detailed home response with counts"""
    members_count: int = 0
    boards_count: int = 0
    owner: Optional["UserResponse"] = None
    
    model_config = {"from_attributes": True}

class HomeWithRole(BaseModel):
    """Home with user's role in that home"""
    id: UUID
    name: str
    address: Optional[str] = None
    role: str  # 'owner' or 'member'
    created_at: datetime
    
    model_config = {"from_attributes": True}

class HomeListResponse(BaseModel):
    """User's homes list response"""
    items: list[HomeWithRole]
    total: int


# ============================================
# HOME MEMBERS
# ============================================

class MemberInvite(BaseModel):
    """Invite member to home request"""
    email: str = Field(..., description="Email of user to invite")
    role: str = Field("member", description="Role: 'owner' or 'member'")


class MemberResponse(BaseModel):
    """Member response model"""
    id: UUID
    user_id: UUID
    role: str
    added_at: datetime
    user: Optional["UserResponse"] = None
    
    model_config = {"from_attributes": True}


class MemberListResponse(BaseModel):
    """Home members list response"""
    items: list[MemberResponse]
    total: int


class MemberUpdateRole(BaseModel):
    """Update member role request (transfer ownership)"""
    role: str = Field(..., description="New role: 'owner' or 'member'")


class MemberRemoveResponse(BaseModel):
    """Remove member response"""
    message: str = "Member removed successfully"


class LeaveHomeResponse(BaseModel):
    """Leave home response"""
    message: str = "Left home successfully"


# ============================================
# FLOOR & ROOM
# ============================================

class FloorCreate(BaseModel):
    """Create floor request"""
    name: str = Field(..., min_length=1, max_length=255)
    floor_number: int = Field(..., ge=0, le=100)


class FloorResponse(BaseModel):
    """Floor response model"""
    id: UUID
    name: str
    floor_number: int
    rooms_count: int = 0
    created_at: datetime
    
    model_config = {"from_attributes": True}


class RoomCreate(BaseModel):
    """Create room request"""
    name: str = Field(..., min_length=1, max_length=255)
    template_type: Optional[str] = Field(None, description="rectangle_3x4, square_3x3, l_shape, etc.")
    position_x: float = 0.0
    position_y: float = 0.0
    width: float = 100.0
    height: float = 100.0


class RoomUpdate(BaseModel):
    """Update room request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class RoomResponse(BaseModel):
    """Room response model"""
    id: UUID
    name: str
    template_type: Optional[str] = None
    position_x: float
    position_y: float
    width: float
    height: float
    devices_count: int = 0
    created_at: datetime
    
    model_config = {"from_attributes": True}


# Forward references
from app.schemas.user import UserResponse
HomeDetailResponse.model_rebuild()
MemberResponse.model_rebuild()