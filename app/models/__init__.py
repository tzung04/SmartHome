"""
SQLAlchemy Models
All database models for Smart Home IoT system
"""
from app.core.database import Base

# Import all models to register with SQLAlchemy
from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetOTP
from app.models.home import Home, HomeMember, MemberRole
from app.models.floor import Floor, Room
from app.models.board import Board, BoardStatus
from app.models.device import Device, DeviceType
from app.models.history import DeviceHistory, SensorData
from app.models.timer import Timer, TimerStatus
from app.models.access_control import AccessCard, AccessLog, AccessResult
from app.models.firmware import Firmware

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