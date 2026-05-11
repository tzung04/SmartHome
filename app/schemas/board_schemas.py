"""
Board Pydantic schemas
Board pairing and management request/response models
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

# ============================================
# BOARD RESPONSE
# ============================================

class BoardResponse(BaseModel):
    """Board response model"""
    id: UUID
    mac_address: str
    board_type: str
    name: Optional[str] = None
    firmware_version: Optional[str] = None
    status: str  # 'unpaired', 'paired', 'online', 'offline'
    last_seen: Optional[datetime] = None
    paired_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class BoardDetailResponse(BoardResponse):
    """Detailed board response with relationships"""
    home_id: Optional[UUID] = None
    devices_count: int = 0
    
    model_config = {"from_attributes": True}


class BoardListResponse(BaseModel):
    """Boards list response"""
    items: list[BoardDetailResponse]
    total: int


# ============================================
# BOARD PAIRING
# ============================================

class BoardPair(BaseModel):
    """Pair board to home request"""
    mac_address: str = Field(..., pattern=r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
    home_id: UUID


class BoardPairResponse(BaseModel):
    """Board pairing response"""
    board: BoardResponse
    devices: list["DeviceResponse"]
    message: str = "Board paired successfully"


# ============================================
# BOARD UPDATE
# ============================================

class BoardUpdate(BaseModel):
    """Update board request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)

# ============================================
# OTA UPDATE
# ============================================

class BoardOTARequest(BaseModel):
    """Trigger OTA update request"""
    firmware_id: UUID


class BoardOTAResponse(BaseModel):
    """OTA update response"""
    board_id: UUID
    status: str = "initiated"
    target_version: str
    message: str = "OTA update initiated"


# ============================================
# BOARD REGISTRATION (from firmware)
# ============================================

class BoardRegister(BaseModel):
    """Board registration message from firmware"""
    mac: str
    board_type: str
    firmware_version: str
    ip: Optional[str] = None


# ============================================
# BOARD HEARTBEAT (from firmware)
# ============================================

class BoardHeartbeat(BaseModel):
    """Board heartbeat message"""
    uptime: int  # seconds
    free_heap: int  # bytes
    rssi: int  # WiFi signal strength
    timestamp: datetime


# Forward references
from app.schemas.device_schemas import DeviceResponse
BoardPairResponse.model_rebuild()
BoardDetailResponse.model_rebuild()