"""
Device Pydantic schemas
Device control and monitoring request/response models
"""
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================
# DEVICE CONTROL
# ============================================

class DeviceControl(BaseModel):
    """Control device request"""
    action: str = Field(..., description="Action to perform: 'set_state'")
    state: dict[str, Any] = Field(..., description="Target state, e.g. {'is_on': true}")


class DeviceControlResponse(BaseModel):
    """Device control response"""
    device_id: UUID
    state: dict[str, Any]
    timestamp: datetime
    message: str = "Command sent successfully"


# ============================================
# DEVICE UPDATE
# ============================================

class DeviceUpdate(BaseModel):
    """Update device request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    room_id: Optional[UUID] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


# ============================================
# DEVICE RESPONSE
# ============================================

class DeviceResponse(BaseModel):
    """Device response model"""
    id: UUID
    board_id: UUID
    room_id: Optional[UUID] = None
    device_type: str
    name: str
    gpio: Optional[int] = None
    state: dict[str, Any]
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class DeviceDetailResponse(DeviceResponse):
    """Detailed device response with board info"""
    board: Optional["BoardResponse"] = None
    
    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    """Devices list response"""
    items: list[DeviceDetailResponse]
    total: int


# ============================================
# DEVICE HISTORY
# ============================================

class DeviceHistoryEntry(BaseModel):
    """Device history entry"""
    id: UUID
    action: str
    old_state: Optional[dict[str, Any]] = None
    new_state: Optional[dict[str, Any]] = None
    triggered_by: Optional["UserResponse"] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class DeviceHistoryResponse(BaseModel):
    """Device history paginated response"""
    items: list[DeviceHistoryEntry]
    total: int
    page: int
    limit: int
    pages: int


# ============================================
# SENSOR DATA
# ============================================

class SensorDataEntry(BaseModel):
    """Sensor data entry"""
    id: UUID
    data: dict[str, Any]
    is_downsampled: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class SensorDataResponse(BaseModel):
    """Sensor data paginated response"""
    items: list[SensorDataEntry]
    total: int
    page: int
    limit: int
    pages: int


class SensorDataLatest(BaseModel):
    """Latest sensor reading"""
    data: dict[str, Any]
    timestamp: datetime


# Forward references
from app.schemas.board_schemas import BoardResponse
from app.schemas.user_schemas import UserResponse
DeviceDetailResponse.model_rebuild()
DeviceHistoryEntry.model_rebuild()