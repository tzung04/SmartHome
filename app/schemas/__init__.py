"""
Pydantic Schemas
Request and response models for all API endpoints
"""

# Auth schemas
from app.schemas.auth import (
    UserRegister,
    UserRegisterResponse,
    UserLogin,
    TokenResponse,
    TokenRefresh,
    TokenRefreshResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    UserResponse,
    AuthSuccessResponse,
    AuthErrorResponse,
)

# User schemas
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserDetailResponse,
    UserListResponse,
    UserBanRequest,
    UserBanResponse,
)

# Home schemas
from app.schemas.home import (
    HomeCreate,
    HomeUpdate,
    HomeResponse,
    HomeDetailResponse,
    HomeListResponse,
    HomeWithRole,
    MemberInvite,
    MemberResponse,
    MemberListResponse,
    MemberUpdateRole,
    MemberRemoveResponse,
    LeaveHomeResponse,
    FloorCreate,
    FloorResponse,
    RoomCreate,
    RoomUpdate,
    RoomResponse,
)

# Board schemas
from app.schemas.board import (
    BoardPair,
    BoardPairResponse,
    BoardUpdate,
    BoardResponse,
    BoardDetailResponse,
    BoardListResponse,
    BoardOTARequest,
    BoardOTAResponse,
    BoardRegister,
    BoardHeartbeat,
)

# Device schemas
from app.schemas.device import (
    DeviceControl,
    DeviceControlResponse,
    DeviceUpdate,
    DeviceResponse,
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceHistoryEntry,
    DeviceHistoryResponse,
    SensorDataEntry,
    SensorDataResponse,
    SensorDataLatest,
)

# Timer schemas
from app.schemas.timer import (
    TimerCreate,
    TimerResponse,
    TimerDetailResponse,
    TimerListResponse,
    TimerCancelResponse,
)

# Access control schemas
from app.schemas.access_control import (
    CardCreate,
    CardUpdate,
    CardResponse,
    CardListResponse,
    CardDeactivateResponse,
    CardLearnRequest,
    CardLearnResponse,
    CardLearnedEvent,
    AccessLogCreate,
    AccessLogResponse,
    AccessLogDetailResponse,
    AccessLogListResponse,
    AccessLogImageUploadResponse,
)

# Firmware schemas
from app.schemas.firmware import (
    FirmwareUpload,
    FirmwareResponse,
    FirmwareDetailResponse,
    FirmwareListResponse,
    FirmwareDeleteResponse,
    FirmwareUpdate,
)

__all__ = [
    # Auth
    "UserRegister",
    "UserRegisterResponse",
    "UserLogin",
    "TokenResponse",
    "TokenRefresh",
    "TokenRefreshResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "ChangePasswordRequest",
    "ChangePasswordResponse",
    "UserResponse",
    "AuthSuccessResponse",
    "AuthErrorResponse",
    
    # User
    "UserCreate",
    "UserUpdate",
    "UserDetailResponse",
    "UserListResponse",
    "UserBanRequest",
    "UserBanResponse",
    
    # Home
    "HomeCreate",
    "HomeUpdate",
    "HomeResponse",
    "HomeDetailResponse",
    "HomeListResponse",
    "HomeWithRole",
    "MemberInvite",
    "MemberResponse",
    "MemberListResponse",
    "MemberUpdateRole",
    "MemberRemoveResponse",
    "LeaveHomeResponse",
    "FloorCreate",
    "FloorResponse",
    "RoomCreate",
    "RoomUpdate",
    "RoomResponse",
    
    # Board
    "BoardPair",
    "BoardPairResponse",
    "BoardUpdate",
    "BoardResponse",
    "BoardDetailResponse",
    "BoardListResponse",
    "BoardOTARequest",
    "BoardOTAResponse",
    "BoardRegister",
    "BoardHeartbeat",
    
    # Device
    "DeviceControl",
    "DeviceControlResponse",
    "DeviceUpdate",
    "DeviceResponse",
    "DeviceDetailResponse",
    "DeviceListResponse",
    "DeviceHistoryEntry",
    "DeviceHistoryResponse",
    "SensorDataEntry",
    "SensorDataResponse",
    "SensorDataLatest",
    
    # Timer
    "TimerCreate",
    "TimerResponse",
    "TimerDetailResponse",
    "TimerListResponse",
    "TimerCancelResponse",
    
    # Access Control
    "CardCreate",
    "CardUpdate",
    "CardResponse",
    "CardListResponse",
    "CardDeactivateResponse",
    "CardLearnRequest",
    "CardLearnResponse",
    "CardLearnedEvent",
    "AccessLogCreate",
    "AccessLogResponse",
    "AccessLogDetailResponse",
    "AccessLogListResponse",
    "AccessLogImageUploadResponse",
    
    # Firmware
    "FirmwareUpload",
    "FirmwareResponse",
    "FirmwareDetailResponse",
    "FirmwareListResponse",
    "FirmwareDeleteResponse",
    "FirmwareUpdate",
]