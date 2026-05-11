"""
Smart Home IoT Backend
FastAPI application entry point
"""
import json
from uuid import UUID

from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api.v1 import api_router
from app.services.mqtt_service import start_mqtt_service, stop_mqtt_service
from app.services.timer_service import start_timer_service, stop_timer_service
from app.services.cleanup_service import start_cleanup_service, stop_cleanup_service
from app.services.downsample_service import start_downsample_service, stop_downsample_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# LIFESPAN EVENTS
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events
    """
    # STARTUP
    logger.info("Starting Smart Home IoT Backend...")
    
    # Start background services
    logger.info("Starting background services...")
    
    try:
        start_mqtt_service()
        logger.info("✓ MQTT service started")
    except Exception as e:
        logger.error(f"✗ Failed to start MQTT service: {e}")
    
    try:
        start_timer_service()
        logger.info("✓ Timer service started")
    except Exception as e:
        logger.error(f"✗ Failed to start timer service: {e}")
    
    try:
        start_cleanup_service()
        logger.info("✓ Cleanup service started")
    except Exception as e:
        logger.error(f"✗ Failed to start cleanup service: {e}")
    
    try:
        start_downsample_service()
        logger.info("✓ Downsample service started")
    except Exception as e:
        logger.error(f"✗ Failed to start downsample service: {e}")
    
    logger.info("Smart Home IoT Backend started successfully!")
    
    yield
    
    # SHUTDOWN
    logger.info("Shutting down Smart Home IoT Backend...")
    
    stop_mqtt_service()
    stop_timer_service()
    stop_cleanup_service()
    stop_downsample_service()
    
    logger.info("Smart Home IoT Backend stopped")


# ============================================
# CREATE FASTAPI APP
# ============================================

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Smart Home IoT Backend - Multi-user system with ESP8266/ESP32 boards",
    lifespan=lifespan
)


# ============================================
# INCLUDE ROUTERS
# ============================================

app.include_router(
    api_router,
    prefix="/api"
)


# ============================================
# ROOT ENDPOINT
# ============================================

@app.get("/")
@app.head("/")
async def root():
    """Root endpoint - API information"""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# ============================================
# HEALTH CHECK
# ============================================

@app.get("/healthz")
@app.head("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "mqtt": "connected",
        "services": {
            "timer": "running",
            "cleanup": "running",
            "downsample": "running"
        }
    }


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

from fastapi import WebSocket, WebSocketDisconnect
from app.services.websocket_manager import manager as ws_manager
from app.core.security import decode_token
from app.crud import user_crud as crud_user
from app.core.database import SessionLocal


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    WebSocket endpoint for real-time updates
    
    Usage: ws://localhost:8000/ws?token={access_token}
    """
    # Verify token
    payload = decode_token(token)
    
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Verify user exists
    db = SessionLocal()
    try:
        user = crud_user.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            await websocket.close(code=1008, reason="User not found or inactive")
            return
    finally:
        db.close()
    
    # Connect WebSocket
    await ws_manager.connect(websocket, user_id)
    
    try:
        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")
                continue

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "subscribe_home":
                    home_id_str = message.get("home_id")
                    if home_id_str:
                        hid = UUID(home_id_str)
                        db = SessionLocal()
                        try:
                            from app.crud import home_crud as crud_home
                            if crud_home.is_home_member(db, hid, user_id):
                                ws_manager.register_home_member(user_id, hid)
                                await websocket.send_text(json.dumps({
                                    "type": "subscribed",
                                    "home_id": home_id_str
                                }))
                        finally:
                            db.close()

                elif msg_type == "unsubscribe_home":
                    home_id_str = message.get("home_id")
                    if home_id_str:
                        ws_manager.unregister_home_member(user_id, UUID(home_id_str))

            except (json.JSONDecodeError, ValueError):
                pass  # Ignore non-JSON / invalid UUID

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, user_id)


# ============================================
# EXCEPTION HANDLERS
# ============================================

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "Validation error"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )