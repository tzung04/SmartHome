"""
WebSocket Manager
Manages WebSocket connections for real-time updates
"""
from typing import Dict, Set, Optional
from uuid import UUID
from fastapi import WebSocket
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager

    Features:
    - User-based connections (multiple devices per user)
    - Home-based broadcasting
    - Device state updates
    - Board status updates
    - Access log notifications (2 bước: event trước, image_ready sau)
    """

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.user_connections: Dict[UUID, Set[WebSocket]] = {}

        # home_id -> set of user_ids
        self.home_members: Dict[UUID, Set[UUID]] = {}

    # ============================================
    # CONNECTION MANAGEMENT
    # ============================================

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """
        Accept WebSocket connection

        Args:
            websocket: WebSocket instance
            user_id: User UUID
        """
        await websocket.accept()

        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()

        self.user_connections[user_id].add(websocket)

        logger.info(f"WebSocket connected: user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """
        Remove WebSocket connection

        Args:
            websocket: WebSocket instance
            user_id: User UUID
        """
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)

            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

                # Cleanup home subscriptions khi user không còn kết nối nào
                for home_id in list(self.home_members.keys()):
                    self.home_members[home_id].discard(user_id)
                    if not self.home_members[home_id]:
                        del self.home_members[home_id]

        logger.info(f"WebSocket disconnected: user {user_id}")

    def register_home_member(self, user_id: UUID, home_id: UUID):
        """Register user as member of home for broadcasting"""
        if home_id not in self.home_members:
            self.home_members[home_id] = set()

        self.home_members[home_id].add(user_id)

    def unregister_home_member(self, user_id: UUID, home_id: UUID):
        """Unregister user from home"""
        if home_id in self.home_members:
            self.home_members[home_id].discard(user_id)

            if not self.home_members[home_id]:
                del self.home_members[home_id]

    # ============================================
    # MESSAGING
    # ============================================

    async def send_personal_message(self, message: dict, user_id: UUID):
        """Send message to specific user (all their connections)"""
        if user_id not in self.user_connections:
            return

        message_json = json.dumps(message)

        disconnected = set()

        for websocket in self.user_connections[user_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {str(e)}")
                disconnected.add(websocket)

        for websocket in disconnected:
            self.user_connections[user_id].discard(websocket)

    async def broadcast_to_home(self, message: dict, home_id: UUID):
        """Broadcast message to all members of a home"""
        if home_id not in self.home_members:
            return

        tasks = []
        for user_id in self.home_members[home_id]:
            tasks.append(self.send_personal_message(message, user_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users (admin use)"""
        message_json = json.dumps(message)

        for connections in self.user_connections.values():
            for websocket in connections:
                try:
                    await websocket.send_text(message_json)
                except Exception:
                    continue

    # ============================================
    # EVENT NOTIFICATIONS
    # ============================================

    async def notify_device_state_change(
        self,
        home_id: UUID,
        device_id: UUID,
        new_state: dict
    ):
        """Notify home members about device state change"""
        message = {
            "type": "device_state_change",
            "device_id": str(device_id),
            "state": new_state,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_board_status_change(
        self,
        home_id: UUID,
        board_id: UUID,
        status: str
    ):
        """Notify home members about board status change"""
        message = {
            "type": "board_status_change",
            "board_id": str(board_id),
            "status": status,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_sensor_data(
        self,
        home_id: UUID,
        device_id: UUID,
        data: dict
    ):
        """Notify home members about new sensor data"""
        message = {
            "type": "sensor_data",
            "device_id": str(device_id),
            "data": data,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_access_log(
        self,
        home_id: UUID,
        board_id: UUID,
        card_uid: str,
        result: str,
        image_url: Optional[str] = None
    ):
        message = {
            "type": "access_log",
            "board_id": str(board_id),
            "card_uid": card_uid,
            "result": result,
            "image_url": image_url,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_access_log_image_ready(
        self,
        home_id: UUID,
        log_id: UUID,
        request_id: str,
        image_url: str
    ):
       
        message = {
            "type": "access_log_image_ready",
            "log_id": str(log_id),
            "request_id": request_id,
            "image_url": image_url,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_timer_executed(
        self,
        home_id: UUID,
        timer_id: UUID,
        device_id: UUID,
        success: bool
    ):
        """Notify home members about timer execution"""
        message = {
            "type": "timer_executed",
            "timer_id": str(timer_id),
            "device_id": str(device_id),
            "success": success,
            "timestamp": self._get_timestamp()
        }

        await self.broadcast_to_home(message, home_id)

    async def notify_card_learned(
        self,
        user_id: UUID,
        board_id: UUID,
        card_uid: str
    ):
        """
        Notify card owner (home owner) về thẻ mới được học.
        Chỉ gửi tới user cụ thể, không broadcast toàn home.
        """
        message = {
            "type": "card_learned",
            "board_id": str(board_id),
            "card_uid": card_uid,
            "timestamp": self._get_timestamp()
        }
        await self.send_personal_message(message, user_id)

    # ============================================
    # UTILITIES
    # ============================================

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(conns) for conns in self.user_connections.values())

    def get_user_connection_count(self, user_id: UUID) -> int:
        """Get number of connections for a user"""
        return len(self.user_connections.get(user_id, set()))

    def is_user_connected(self, user_id: UUID) -> bool:
        """Check if user has any active connections"""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0


# Global WebSocket manager instance
manager = ConnectionManager()


# Helper functions for easy import
async def connect(websocket: WebSocket, user_id: UUID):
    """Connect WebSocket"""
    await manager.connect(websocket, user_id)


def disconnect(websocket: WebSocket, user_id: UUID):
    """Disconnect WebSocket"""
    manager.disconnect(websocket, user_id)


async def notify_device_state_change(home_id: UUID, device_id: UUID, new_state: dict):
    """Notify device state change"""
    await manager.notify_device_state_change(home_id, device_id, new_state)


async def notify_board_status_change(home_id: UUID, board_id: UUID, status: str):
    """Notify board status change"""
    await manager.notify_board_status_change(home_id, board_id, status)


async def notify_sensor_data(home_id: UUID, device_id: UUID, data: dict):
    """Notify sensor data"""
    await manager.notify_sensor_data(home_id, device_id, data)


async def notify_access_log(
    home_id: UUID,
    board_id: UUID,
    card_uid: str,
    result: str,
    image_url: Optional[str] = None
):
    """Notify access log (bước 1 - chưa có ảnh)"""
    await manager.notify_access_log(home_id, board_id, card_uid, result, image_url)


async def notify_access_log_image_ready(
    home_id: UUID,
    log_id: UUID,
    request_id: str,
    image_url: str
):
    """Notify khi ảnh access log đã upload xong (bước 2)"""
    await manager.notify_access_log_image_ready(home_id, log_id, request_id, image_url)


async def notify_card_learned(user_id: UUID, board_id: UUID, card_uid: str):
    """Notify card learned event to home owner"""
    await manager.notify_card_learned(user_id, board_id, card_uid)