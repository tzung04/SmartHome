"""
Firebase Cloud Messaging Service 
Send push notifications for timer execution, access logs, and board disconnection
"""
import json
import logging
from typing import Optional, Dict, Any, List
from firebase_admin import credentials, messaging, initialize_app
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


class FCMService:
    """
    Enhanced Firebase Cloud Messaging service
    
    Features:
    - Timer execution notifications (success/failed)
    - Access control notifications (granted/denied/unknown)
    - Board offline/online notifications
    - Support for notification preferences
    - Multicast for home members
    """
    
    def __init__(self):
        """Initialize FCM with credentials"""
        try:
            # Parse credentials from JSON string
            cred_dict = json.loads(settings.firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
            initialize_app(cred)
            self.initialized = True
            logger.info("FCM service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FCM: {str(e)}")
            self.initialized = False
    
    def send_notification(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "high",
        click_action: Optional[str] = None
    ) -> bool:
        """
        Send push notification to device
        
        Args:
            fcm_token: Device FCM token
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: Notification priority (high/normal)
            click_action: Action when notification clicked
            
        Returns:
            True if sent successfully
        """
        if not self.initialized:
            logger.warning("FCM not initialized, skipping notification")
            return False
        
        try:
            # Build Android config
            android_config = messaging.AndroidConfig(
                priority=priority,
                notification=messaging.AndroidNotification(
                    sound="default",
                    click_action=click_action
                )
            )
            
            # Build message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=fcm_token,
                android=android_config
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent notification: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return False
    
    def send_multicast(
        self,
        fcm_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "high"
    ) -> int:
        """
        Send notification to multiple devices
        
        Args:
            fcm_tokens: List of device FCM tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: Notification priority
            
        Returns:
            Number of successful sends
        """
        if not self.initialized:
            logger.warning("FCM not initialized, skipping notifications")
            return 0
        
        try:
            # Build Android config
            android_config = messaging.AndroidConfig(
                priority=priority,
                notification=messaging.AndroidNotification(
                    sound="default"
                )
            )
            
            messages = [
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=token,
                    android=android_config
                )
                for token in fcm_tokens
            ]

            response = messaging.send_each(messages)

            success_count = response.success_count
            logger.info(f"Successfully sent {success_count}/{len(fcm_tokens)} notifications")
            
            # Log failed tokens for cleanup
            if response.failure_count > 0:
                failed_tokens = [
                    fcm_tokens[idx] 
                    for idx, resp in enumerate(response.responses) 
                    if not resp.success
                ]
                logger.warning(f"Failed to send to {len(failed_tokens)} tokens: {failed_tokens}")
            
            return response.success_count
            
        except Exception as e:
            logger.error(f"Failed to send multicast: {str(e)}")
            return 0
    
    # ============================================
    # TIMER NOTIFICATIONS
    # ============================================
    
    def notify_timer_executed(
        self,
        fcm_token: str,
        device_name: str,
        success: bool,
        timer_id: str,
        home_name: Optional[str] = None
    ) -> bool:
        """
        Send timer execution notification
        
        Args:
            fcm_token: Device FCM token
            device_name: Name of controlled device
            success: Whether timer executed successfully
            timer_id: Timer UUID
            home_name: Name of home (optional)
            
        Returns:
            True if sent successfully
        """
        if success:
            title = "Timer Executed"
            body = f"{device_name} turned on successfully"
            icon = ""
        else:
            title = "Timer Failed"
            body = f"Failed to turn on {device_name}"
            icon = ""
        
        # Add home context if available
        if home_name:
            body = f"[{home_name}] {body}"
        
        data = {
            "type": "timer_executed",
            "timer_id": timer_id,
            "device_name": device_name,
            "success": str(success).lower(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": icon
        }
        
        return self.send_notification(
            fcm_token=fcm_token,
            title=title,
            body=body,
            data=data,
            priority="high"
        )
    
    def notify_timer_executed_multicast(
        self,
        fcm_tokens: List[str],
        device_name: str,
        success: bool,
        timer_id: str,
        home_name: Optional[str] = None
    ) -> int:
        """Send timer execution notification to multiple devices"""
        if success:
            title = "Timer Executed"
            body = f"{device_name} turned on successfully"
        else:
            title = "Timer Failed"
            body = f"Failed to turn on {device_name}"
        
        if home_name:
            body = f"[{home_name}] {body}"
        
        data = {
            "type": "timer_executed",
            "timer_id": timer_id,
            "device_name": device_name,
            "success": str(success).lower(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return self.send_multicast(fcm_tokens, title, body, data, priority="high")
    
    # ============================================
    # ACCESS CONTROL NOTIFICATIONS
    # ============================================
    
    def notify_access_event(
        self,
        fcm_token: str,
        card_owner: str,
        result: str,
        board_name: Optional[str] = None,
        home_name: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> bool:
        """
        Send access control notification
        
        Args:
            fcm_token: Device FCM token
            card_owner: Name of card owner
            result: Access result (granted/denied/unknown_card)
            board_name: Name of board/door (optional)
            home_name: Name of home (optional)
            image_url: URL of captured image (optional)
            
        Returns:
            True if sent successfully
        """
        # Customize notification based on result
        if result == "granted":
            title = "Access Granted"
            body = f"{card_owner} entered"
            icon = ""
            priority = "normal"
        elif result == "denied":
            title = "Access Denied"
            body = f"{card_owner} - card expired or deactivated"
            icon = ""
            priority = "high"
        else:  # unknown_card
            title = "Unknown Card"
            body = "Unregistered card detected"
            icon = ""
            priority = "high"
        
        # Add location context
        location_parts = []
        if home_name:
            location_parts.append(home_name)
        if board_name:
            location_parts.append(board_name)
        
        if location_parts:
            body = f"[{' - '.join(location_parts)}] {body}"
        
        data = {
            "type": "access_event",
            "card_owner": card_owner,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": icon
        }
        
        # Add image URL if available
        if image_url:
            data["image_url"] = image_url
            data["has_image"] = "true"
        
        return self.send_notification(
            fcm_token=fcm_token,
            title=title,
            body=body,
            data=data,
            priority=priority,
            click_action="ACCESS_LOG_DETAILS"
        )
    
    def notify_access_event_multicast(
        self,
        fcm_tokens: List[str],
        card_owner: str,
        result: str,
        board_name: Optional[str] = None,
        home_name: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> int:
        """Send access event notification to multiple devices"""
        if result == "granted":
            title = "Access Granted"
            body = f"{card_owner} entered"
            priority = "normal"
        elif result == "denied":
            title = "Access Denied"
            body = f"{card_owner} - access denied"
            priority = "high"
        else:
            title = "Unknown Card"
            body = "Unregistered card detected"
            priority = "high"
        
        if home_name and board_name:
            body = f"[{home_name} - {board_name}] {body}"
        
        data = {
            "type": "access_event",
            "card_owner": card_owner,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if image_url:
            data["image_url"] = image_url
            data["has_image"] = "true"
        
        return self.send_multicast(fcm_tokens, title, body, data, priority=priority)
    
    # ============================================
    # BOARD STATUS NOTIFICATIONS
    # ============================================
    
    def notify_board_offline(
        self,
        fcm_token: str,
        board_name: str,
        board_id: str,
        home_name: Optional[str] = None,
        last_seen: Optional[datetime] = None
    ) -> bool:
        """
        Send board offline notification
        
        Args:
            fcm_token: Device FCM token
            board_name: Name of board
            board_id: Board UUID
            home_name: Name of home (optional)
            last_seen: Last seen timestamp (optional)
            
        Returns:
            True if sent successfully
        """
        title = "Board Disconnected"
        body = f"{board_name} went offline"
        
        if home_name:
            body = f"[{home_name}] {body}"
        
        # Add last seen info
        if last_seen:
            time_diff = datetime.now(timezone.utc) - last_seen
            if time_diff.seconds < 60:
                time_str = "just now"
            elif time_diff.seconds < 3600:
                time_str = f"{time_diff.seconds // 60} minutes ago"
            else:
                time_str = f"{time_diff.seconds // 3600} hours ago"
            
            body += f" (last seen {time_str})"
        
        data = {
            "type": "board_offline",
            "board_id": board_id,
            "board_name": board_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": ""
        }
        
        if last_seen:
            data["last_seen"] = last_seen.isoformat()
        
        return self.send_notification(
            fcm_token=fcm_token,
            title=title,
            body=body,
            data=data,
            priority="high",
            click_action="BOARD_STATUS"
        )
    
    def notify_board_online(
        self,
        fcm_token: str,
        board_name: str,
        board_id: str,
        home_name: Optional[str] = None
    ) -> bool:
        """
        Send board online notification
        
        Args:
            fcm_token: Device FCM token
            board_name: Name of board
            board_id: Board UUID
            home_name: Name of home (optional)
            
        Returns:
            True if sent successfully
        """
        title = "Board Connected"
        body = f"{board_name} is back online"
        
        if home_name:
            body = f"[{home_name}] {body}"
        
        data = {
            "type": "board_online",
            "board_id": board_id,
            "board_name": board_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": ""
        }
        
        return self.send_notification(
            fcm_token=fcm_token,
            title=title,
            body=body,
            data=data,
            priority="normal"
        )
    
    def notify_board_status_multicast(
        self,
        fcm_tokens: List[str],
        board_name: str,
        board_id: str,
        is_online: bool,
        home_name: Optional[str] = None
    ) -> int:
        """Send board status notification to multiple devices"""
        if is_online:
            title = "Board Connected"
            body = f"{board_name} is back online"
            icon = ""
            priority = "normal"
        else:
            title = "Board Disconnected"
            body = f"{board_name} went offline"
            icon = ""
            priority = "high"
        
        if home_name:
            body = f"[{home_name}] {body}"
        
        data = {
            "type": "board_online" if is_online else "board_offline",
            "board_id": board_id,
            "board_name": board_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": icon
        }
        
        return self.send_multicast(fcm_tokens, title, body, data, priority=priority)


# ============================================
# GLOBAL INSTANCE
# ============================================

fcm_service: Optional[FCMService] = None

try:
    fcm_service = FCMService()
except Exception:
    logger.warning("FCM service not initialized - push notifications disabled")


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """Send generic push notification"""
    if fcm_service:
        return fcm_service.send_notification(fcm_token, title, body, data)
    return False


# Timer notifications
def notify_timer_executed(
    fcm_token: str,
    device_name: str,
    success: bool,
    timer_id: str,
    home_name: Optional[str] = None
) -> bool:
    """Send timer execution notification"""
    if fcm_service:
        return fcm_service.notify_timer_executed(
            fcm_token, device_name, success, timer_id, home_name
        )
    return False


def notify_timer_executed_to_home_members(
    fcm_tokens: List[str],
    device_name: str,
    success: bool,
    timer_id: str,
    home_name: Optional[str] = None
) -> int:
    """Send timer notification to all home members"""
    if fcm_service:
        return fcm_service.notify_timer_executed_multicast(
            fcm_tokens, device_name, success, timer_id, home_name
        )
    return 0


# Access control notifications
def notify_access_event(
    fcm_token: str,
    card_owner: str,
    result: str,
    board_name: Optional[str] = None,
    home_name: Optional[str] = None,
    image_url: Optional[str] = None
) -> bool:
    """Send access control notification"""
    if fcm_service:
        return fcm_service.notify_access_event(
            fcm_token, card_owner, result, board_name, home_name, image_url
        )
    return False


def notify_access_event_to_home_members(
    fcm_tokens: List[str],
    card_owner: str,
    result: str,
    board_name: Optional[str] = None,
    home_name: Optional[str] = None,
    image_url: Optional[str] = None
) -> int:
    """Send access event notification to all home members"""
    if fcm_service:
        return fcm_service.notify_access_event_multicast(
            fcm_tokens, card_owner, result, board_name, home_name, image_url
        )
    return 0


# Board status notifications
def notify_board_offline(
    fcm_token: str,
    board_name: str,
    board_id: str,
    home_name: Optional[str] = None,
    last_seen: Optional[datetime] = None
) -> bool:
    """Send board offline notification"""
    if fcm_service:
        return fcm_service.notify_board_offline(
            fcm_token, board_name, board_id, home_name, last_seen
        )
    return False


def notify_board_online(
    fcm_token: str,
    board_name: str,
    board_id: str,
    home_name: Optional[str] = None
) -> bool:
    """Send board online notification"""
    if fcm_service:
        return fcm_service.notify_board_online(
            fcm_token, board_name, board_id, home_name
        )
    return False


def notify_board_status_to_home_members(
    fcm_tokens: List[str],
    board_name: str,
    board_id: str,
    is_online: bool,
    home_name: Optional[str] = None
) -> int:
    """Send board status notification to all home members"""
    if fcm_service:
        return fcm_service.notify_board_status_multicast(
            fcm_tokens, board_name, board_id, is_online, home_name
        )
    return 0