"""
SQLAlchemy Models
All database models for Smart Home IoT system
"""
from app.core.database import Base

# Import all models to register with SQLAlchemy
from app.models.user_model import User, UserRole
from app.models.password_reset_model import PasswordResetOTP
from app.models.home_model import Home, HomeMember, MemberRole
from app.models.floor_model import Floor, Room
from app.models.board_model import Board, BoardStatus
from app.models.device_model import Device, DeviceType
from app.models.history_model import DeviceHistory, SensorData
from app.models.timer_model import Timer, TimerStatus
from app.models.access_control_model import AccessCard, AccessLog, AccessResult
from app.models.firmware_model import Firmware

# Export all models and enums
__all__ = [
    # Base
    "Base",
    
    # User & Auth
    "User",
    "UserRole",
    "PasswordResetOTP",
    
    # Home & Members
    "Home",
    "HomeMember",
    "MemberRole",
    
    # Floor Plan
    "Floor",
    "Room",
    
    # Boards & Devices
    "Board",
    "BoardStatus",
    "Device",
    "DeviceType",
    
    # History & Data
    "DeviceHistory",
    "SensorData",
    
    # Timers
    "Timer",
    "TimerStatus",
    
    # Access Control
    "AccessCard",
    "AccessLog",
    "AccessResult",
    
    # Firmware
    "Firmware",
]