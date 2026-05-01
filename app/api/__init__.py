"""
API v1 Routes
All REST API endpoints
"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    admin,
    homes,
    members,
    floors,
    boards,
    devices,
    sensors,
    timers,
    access_control
)

# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(homes.router)
api_router.include_router(members.router)
api_router.include_router(floors.router)
api_router.include_router(boards.router)
api_router.include_router(devices.router)
api_router.include_router(sensors.router)
api_router.include_router(timers.router)
api_router.include_router(access_control.router)

__all__ = ["api_router"]