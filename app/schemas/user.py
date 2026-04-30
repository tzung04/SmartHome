"""
User Pydantic schemas
User CRUD request and response models
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ============================================
# USER BASE
# ============================================

class UserBase(BaseModel):
    """Base user fields"""
    email: EmailStr
    full_name: Optional[str] = None


# ============================================
# USER CREATE (Admin only)
# ============================================

class UserCreate(BaseModel):
    """Create user request (admin)"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = "user"  # 'super_admin' or 'user'


# ============================================
# USER UPDATE
# ============================================

class UserUpdate(BaseModel):
    """Update user request"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None


# ============================================
# USER RESPONSE
# ============================================

class UserResponse(BaseModel):
    """User response model"""
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    """Detailed user response (with additional info)"""
    updated_at: datetime
    
    model_config = {"from_attributes": True}


# ============================================
# USER LIST (Admin)
# ============================================

class UserListResponse(BaseModel):
    """Paginated user list response (admin)"""
    items: list[UserResponse]
    total: int
    page: int
    limit: int
    pages: int


# ============================================
# USER BAN (Admin)
# ============================================

class UserBanRequest(BaseModel):
    """Ban user request (admin)"""
    reason: Optional[str] = Field(None, max_length=500)


class UserBanResponse(BaseModel):
    """Ban user response"""
    user_id: UUID
    is_active: bool
    message: str = "User account disabled"