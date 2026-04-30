"""
Firmware Pydantic schemas
Firmware management request/response models (Super Admin only)
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================
# FIRMWARE UPLOAD
# ============================================

class FirmwareUpload(BaseModel):
    """Upload firmware request (multipart/form-data)"""
    board_type: str = Field(..., description="Board type: 'ESP8266_CONTROL_V1', etc.")
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$', description="Semantic version: '1.0.1'")
    changelog: Optional[str] = Field(None, max_length=2000, description="Release notes")
    # file: UploadFile handled separately in endpoint


# ============================================
# FIRMWARE RESPONSE
# ============================================

class FirmwareResponse(BaseModel):
    """Firmware response model"""
    id: UUID
    board_type: str
    version: str
    file_url: str
    file_size_bytes: Optional[int] = None
    md5_hash: Optional[str] = None
    changelog: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    uploaded_at: datetime
    is_active: bool
    
    model_config = {"from_attributes": True}


class FirmwareDetailResponse(FirmwareResponse):
    """Detailed firmware response with uploader info"""
    uploaded_by_user: Optional["UserResponse"] = None
    
    model_config = {"from_attributes": True}


class FirmwareListResponse(BaseModel):
    """Firmwares list response"""
    items: list[FirmwareDetailResponse]
    total: int


# ============================================
# FIRMWARE DELETE
# ============================================

class FirmwareDeleteResponse(BaseModel):
    """Firmware delete response"""
    firmware_id: UUID
    message: str = "Firmware deleted successfully"


# ============================================
# FIRMWARE UPDATE
# ============================================

class FirmwareUpdate(BaseModel):
    """Update firmware metadata request"""
    changelog: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


# Forward references
from app.schemas.user import UserResponse
FirmwareDetailResponse.model_rebuild()