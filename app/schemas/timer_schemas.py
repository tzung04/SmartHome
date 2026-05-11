"""
Timer Pydantic schemas
Timer scheduling request/response models
"""
from typing import Any, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# ============================================
# TIMER CREATE
# ============================================

class TimerCreate(BaseModel):
    """Create timer request"""
    target_state: dict[str, Any] = Field(..., description="Target state, e.g. {'is_on': true}")
    execute_at: datetime = Field(..., description="When to execute timer (ISO format)")
    
    @field_validator('execute_at')
    @classmethod
    def validate_execute_at(cls, v: datetime) -> datetime:
        """Validate execute_at is in the future"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Make execute_at timezone-aware if it isn't
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        
        if v <= now:
            raise ValueError('execute_at must be in the future')
        
        return v


# ============================================
# TIMER RESPONSE
# ============================================

class TimerResponse(BaseModel):
    """Timer response model"""
    id: UUID
    device_id: UUID
    created_by: UUID
    target_state: dict[str, Any]
    execute_at: datetime
    status: str  # 'pending', 'executed', 'failed', 'cancelled'
    retry_count: int
    executed_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TimerDetailResponse(TimerResponse):
    """Detailed timer response with device info"""
    device: Optional["DeviceResponse"] = None
    
    model_config = {"from_attributes": True}


class TimerListResponse(BaseModel):
    """Timers list response"""
    items: list[TimerDetailResponse]
    total: int


# ============================================
# TIMER CANCEL
# ============================================

class TimerCancelResponse(BaseModel):
    """Timer cancel response"""
    timer_id: UUID
    status: str = "cancelled"
    message: str = "Timer cancelled successfully"


# Forward references
from app.schemas.device_schemas import DeviceResponse
TimerDetailResponse.model_rebuild()