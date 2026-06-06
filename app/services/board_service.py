"""
Board Service
Auto-device creation based on board templates
"""
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
import logging

from app.models.board_model import Board
from app.models.device_model import Device, DeviceType
from app.crud import device_crud as crud_device
from app.utils.board_templates import BOARD_TEMPLATES

logger = logging.getLogger(__name__)


# ============================================
# DEVICE INITIAL STATES
# ============================================

def get_initial_device_state(device_type: DeviceType) -> dict:
    """
    Get initial state for device type
    
    Args:
        device_type: Device type enum
        
    Returns:
        Initial state dictionary
    """
    if device_type == DeviceType.RELAY:
        return {"is_on": False}
    
    elif device_type == DeviceType.DHT11:
        return {"temperature": 0.0, "humidity": 0.0}
    
    elif device_type == DeviceType.PIR:
        return {"motion_detected": False}
    
    elif device_type == DeviceType.LDR:
        return {"is_dark": 0}
    
    elif device_type == DeviceType.RC522:
        return {"last_card_uid": None, "learning_mode": False}
    
    elif device_type == DeviceType.CAMERA:
        return {"resolution": "160x120", "quality": 10}
    
    elif device_type == DeviceType.DOOR_LOCK:
        return {"is_locked": True}
    
    else:
        return {}


# ============================================
# BOARD SERVICE
# ============================================

class BoardService:
    """
    Board service for auto-device creation
    """
    
    @staticmethod
    def get_board_template(board_type: str) -> dict:
        """
        Get board template by type
        
        Args:
            board_type: Board type identifier
            
        Returns:
            Template dict or None if not found
        """
        return BOARD_TEMPLATES.get(board_type)
    
    @staticmethod
    def create_devices_for_board(db: Session, board: Board) -> List[Device]:
        """
        Create devices for a board based on its template
        
        Args:
            db: Database session
            board: Board model instance
            
        Returns:
            List of created devices
        """
        template = BOARD_TEMPLATES.get(board.board_type)
        
        if not template:
            logger.warning(f"No template found for board type: {board.board_type}")
            return []
        
        devices = []
        
        for device_config in template["devices"]:
            try:
                # Get initial state
                initial_state = get_initial_device_state(device_config["type"])
                
                # Create device
                device = crud_device.create_device(
                    db=db,
                    board_id=board.id,
                    device_type=device_config["type"],
                    name=device_config["name"],
                    gpio=device_config.get("gpio"),
                    state=initial_state
                )
                
                devices.append(device)
                logger.info(f"Created device: {device.name} (type: {device.device_type})")
                
            except Exception as e:
                logger.error(f"Error creating device: {str(e)}")
                continue
        
        return devices
    
    @staticmethod
    def get_device_count(board_type: str) -> int:
        """
        Get expected device count for board type
        
        Args:
            board_type: Board type identifier
            
        Returns:
            Number of devices
        """
        template = BOARD_TEMPLATES.get(board_type)
        return len(template["devices"]) if template else 0
    
    @staticmethod
    def is_valid_board_type(board_type: str) -> bool:
        """
        Check if board type is valid
        
        Args:
            board_type: Board type identifier
            
        Returns:
            True if valid
        """
        return board_type in BOARD_TEMPLATES
    
    @staticmethod
    def get_all_board_types() -> List[str]:
        """
        Get list of all supported board types
        
        Returns:
            List of board type identifiers
        """
        return list(BOARD_TEMPLATES.keys())
    
    @staticmethod
    def get_board_info(board_type: str) -> dict:
        """
        Get board information
        
        Args:
            board_type: Board type identifier
            
        Returns:
            Dict with board info (name, device count, device types)
        """
        template = BOARD_TEMPLATES.get(board_type)
        
        if not template:
            return {}
        
        return {
            "board_type": board_type,
            "name": template["name"],
            "device_count": len(template["devices"]),
            "device_types": [d["type"].value for d in template["devices"]]
        }


# Global board service instance
board_service = BoardService()


# Helper functions for easy import
def create_devices_for_board(db: Session, board: Board) -> List[Device]:
    """Create devices for a board"""
    return board_service.create_devices_for_board(db, board)


def is_valid_board_type(board_type: str) -> bool:
    """Check if board type is valid"""
    return board_service.is_valid_board_type(board_type)


def get_board_info(board_type: str) -> dict:
    """Get board information"""
    return board_service.get_board_info(board_type)


def get_all_board_types() -> List[str]:
    """Get all supported board types"""
    return board_service.get_all_board_types()