"""
Access Control Pydantic schemas
RFID card and access log request/response models
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================
# ACCESS CARD
# ============================================

class CardCreate(BaseModel):
    """Create access card request"""
    card_uid: str = Field(..., min_length=4, max_length=20, description="RFID card UID (hex)")
    owner_name: str = Field(..., min_length=1, max_length=255)
    owner_user_id: Optional[UUID] = None
    valid_until: Optional[datetime] = Field(None, description="Expiry date (null = permanent)")


class CardUpdate(BaseModel):
    """Update access card request"""
    owner_name: Optional[str] = Field(None, min_length=1, max_length=255)
    valid_until: Optional[datetime] = None


class CardResponse(BaseModel):
    """Access card response model"""
    id: UUID
    card_uid: str
    owner_name: str
    owner_user_id: Optional[UUID] = None
    is_active: bool
    valid_from: datetime
    valid_until: Optional[datetime] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class CardListResponse(BaseModel):
    """Access cards list response"""
    items: list[CardResponse]
    total: int


class CardDeactivateResponse(BaseModel):
    """Deactivate card response"""
    card_id: UUID
    is_active: bool
    message: str = "Card deactivated successfully"


# ============================================
# CARD LEARNING
# ============================================

class CardLearnRequest(BaseModel):
    """Trigger card learning mode request"""
    timeout: int = Field(30, ge=10, le=60, description="Learning mode timeout in seconds")


class CardLearnResponse(BaseModel):
    """Card learning response"""
    board_id: UUID
    status: str = "learning"
    timeout: int
    message: str = "Board entered learning mode"


class CardLearnedEvent(BaseModel):
    """Card learned event from board"""
    card_uid: str
    timestamp: datetime


# ============================================
# ACCESS LOG
# ============================================

class AccessLogCreate(BaseModel):
    """Create access log request (from board)"""
    board_mac: str = Field(..., pattern=r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
    card_uid: str
    result: str = Field(..., description="'granted', 'denied', or 'unknown_card'")
    image_base64: Optional[str] = Field(None, description="Base64 encoded image")
    timestamp: datetime


class AccessLogResponse(BaseModel):
    """Access log response model"""
    id: UUID
    board_id: UUID
    card_uid: str
    card: Optional[CardResponse] = None
    result: str
    image_url: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class AccessLogDetailResponse(AccessLogResponse):
    """Detailed access log with board info"""
    board: Optional["BoardResponse"] = None
    
    model_config = {"from_attributes": True}


class AccessLogListResponse(BaseModel):
    """Access logs paginated response"""
    items: list[AccessLogDetailResponse]
    total: int
    page: int
    limit: int
    pages: int


# ============================================
# ACCESS LOG IMAGE UPLOAD
# ============================================

class AccessLogImageUploadResponse(BaseModel):
    """Access log image upload response"""
    log_id: UUID
    image_url: str
    message: str = "Access log saved successfully"


# Forward references
from app.schemas.board_schemas import BoardResponse
AccessLogDetailResponse.model_rebuild()