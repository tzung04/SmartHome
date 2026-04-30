"""
MQTT Service
MQTT client for board communication
"""
import json
import logging
from typing import Optional, Callable
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import board as crud_board
from app.crud import device as crud_device
from app.crud import access_control as crud_access_control
from app.services.websocket_manager import manager as ws_manager
from app.services.storage_service import upload_access_log_image
from app.models.board import BoardStatus
from app.models.access_control import AccessResult

logger = logging.getLogger(__name__)


class MQTTService:
    """
    MQTT service for board communication
    
    Topic structure:
    - boards/{board_id}/status          - Board status (online/offline)
    - boards/{board_id}/state           - Device state updates
    - boards/{board_id}/sensor          - Sensor data
    - boards/{board_id}/control         - Control commands (from server)
    - boards/{board_id}/card/learned    - Card learned event
    - boards/{board_id}/access          - Access log
    - boards/{board_id}/ota             - OTA commands
    """
    
    def __init__(self):
        """Initialize MQTT client"""
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        
    def start(self):
        """Start MQTT service"""
        try:
            # Create MQTT client
            self.client = mqtt.Client(
                client_id=settings.mqtt_client_id,
                clean_session=True
            )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Set credentials
            self.client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password
            )
            
            # Enable TLS if configured
            if settings.mqtt_use_tls:
                self.client.tls_set()
            
            # Connect
            self.client.connect(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=60
            )
            
            # Start loop
            self.client.loop_start()
            
            logger.info("MQTT service started")
            
        except Exception as e:
            logger.error(f"Error starting MQTT service: {str(e)}")
            raise
    
    def stop(self):
        """Stop MQTT service"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT service stopped")
    
    # ============================================
    # CALLBACKS
    # ============================================
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Subscribe to topics
            self._subscribe_topics()
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"MQTT message: {topic} = {payload}")
            
            # Route message to handler
            if '/status' in topic:
                self._handle_board_status(topic, payload)
            elif '/state' in topic:
                self._handle_device_state(topic, payload)
            elif '/sensor' in topic:
                self._handle_sensor_data(topic, payload)
            elif '/card/learned' in topic:
                self._handle_card_learned(topic, payload)
            elif '/access' in topic:
                self._handle_access_log(topic, payload)
            else:
                logger.warning(f"Unhandled MQTT topic: {topic}")
                
        except Exception as e:
            logger.error(f"Error handling MQTT message: {str(e)}")
    
    def _subscribe_topics(self):
        """Subscribe to MQTT topics"""
        topics = [
            ("boards/+/status", 0),
            ("boards/+/state", 0),
            ("boards/+/sensor", 0),
            ("boards/+/card/learned", 0),
            ("boards/+/access", 0),
        ]
        
        self.client.subscribe(topics)
        logger.info(f"Subscribed to {len(topics)} MQTT topics")
    
    # ============================================
    # MESSAGE HANDLERS
    # ============================================
    
    def _handle_board_status(self, topic: str, payload: str):
        """
        Handle board status message
        
        Topic: boards/{board_id}/status
        Payload: {"status": "online", "uptime": 1234, "free_heap": 25000, "rssi": -65}
        """
        try:
            # Extract board_id from topic
            board_mac = topic.split('/')[1]
            
            data = json.loads(payload)
            status = data.get('status', 'online')
            
            db = SessionLocal()
            try:
                # Update board heartbeat
                board = crud_board.update_board_heartbeat(db, board_mac)
                
                if board and board.home_id:
                    # Notify WebSocket clients
                    import asyncio
                    asyncio.create_task(
                        ws_manager.notify_board_status_change(
                            board.home_id,
                            board.id,
                            status
                        )
                    )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling board status: {str(e)}")
    
    def _handle_device_state(self, topic: str, payload: str):
        """
        Handle device state update
        
        Topic: boards/{board_id}/state
        Payload: {"device_gpio": 5, "state": {"is_on": true}}
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            
            device_gpio = data.get('device_gpio')
            new_state = data.get('state', {})
            
            db = SessionLocal()
            try:
                # Find board
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return
                
                # Find device by GPIO
                devices = crud_device.get_board_devices(db, board.id)
                device = next((d for d in devices if d.gpio == device_gpio), None)
                
                if device:
                    # Update device state
                    crud_device.update_device_state(
                        db, device.id, new_state, triggered_by=None
                    )
                    
                    # Notify WebSocket clients
                    if board.home_id:
                        import asyncio
                        asyncio.create_task(
                            ws_manager.notify_device_state_change(
                                board.home_id,
                                device.id,
                                new_state
                            )
                        )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling device state: {str(e)}")
    
    def _handle_sensor_data(self, topic: str, payload: str):
        """
        Handle sensor data
        
        Topic: boards/{board_id}/sensor
        Payload: {"device_gpio": 4, "data": {"temperature": 25.5, "humidity": 60.2}}
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            
            device_gpio = data.get('device_gpio')
            sensor_data = data.get('data', {})
            
            db = SessionLocal()
            try:
                # Find board and device
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return
                
                devices = crud_device.get_board_devices(db, board.id)
                device = next((d for d in devices if d.gpio == device_gpio), None)
                
                if device:
                    # Save sensor data
                    crud_device.create_sensor_data(
                        db, device.id, sensor_data, is_downsampled=False
                    )
                    
                    # Notify WebSocket clients
                    if board.home_id:
                        import asyncio
                        asyncio.create_task(
                            ws_manager.notify_sensor_data(
                                board.home_id,
                                device.id,
                                sensor_data
                            )
                        )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling sensor data: {str(e)}")
    
    def _handle_card_learned(self, topic: str, payload: str):
        """
        Handle card learned event
        
        Topic: boards/{board_id}/card/learned
        Payload: {"card_uid": "AABBCCDD"}
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            card_uid = data.get('card_uid')
            
            logger.info(f"Card learned on board {board_mac}: {card_uid}")
            
            # Card will be created via API endpoint when user provides owner info
            
        except Exception as e:
            logger.error(f"Error handling card learned: {str(e)}")
    
    def _handle_access_log(self, topic: str, payload: str):
        """
        Handle access log
        
        Topic: boards/{board_id}/access
        Payload: {"card_uid": "AABBCCDD", "result": "granted", "image_base64": "..."}
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            
            card_uid = data.get('card_uid')
            result = data.get('result', 'unknown_card')
            image_base64 = data.get('image_base64')
            
            db = SessionLocal()
            try:
                # Find board
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return
                
                # Upload image if provided
                image_url = None
                if image_base64:
                    image_url = upload_access_log_image(board_mac, image_base64)
                
                # Create access log
                access_log = crud_access_control.create_access_log(
                    db,
                    board_id=board.id,
                    card_uid=card_uid,
                    result=AccessResult(result),
                    image_url=image_url
                )
                
                # Notify WebSocket clients
                if board.home_id:
                    import asyncio
                    asyncio.create_task(
                        ws_manager.notify_access_log(
                            board.home_id,
                            board.id,
                            card_uid,
                            result,
                            image_url
                        )
                    )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling access log: {str(e)}")
    
    # ============================================
    # PUBLISH METHODS
    # ============================================
    
    def publish_device_control(self, board_id: str, device_gpio: int, state: dict) -> bool:
        """
        Publish device control command
        
        Args:
            board_id: Board ID or MAC
            device_gpio: Device GPIO pin
            state: Target state
            
        Returns:
            True if published successfully
        """
        try:
            topic = f"boards/{board_id}/control"
            payload = json.dumps({
                "device_gpio": device_gpio,
                "state": state
            })
            
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Error publishing device control: {str(e)}")
            return False
    
    def publish_card_sync(self, board_id: str, cards: list) -> bool:
        """
        Publish card sync to board
        
        Args:
            board_id: Board ID or MAC
            cards: List of card UIDs
            
        Returns:
            True if published successfully
        """
        try:
            topic = f"boards/{board_id}/card/sync"
            payload = json.dumps({"cards": cards})
            
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Error publishing card sync: {str(e)}")
            return False
    
    def publish_card_learn(self, board_id: str, timeout: int = 30) -> bool:
        """
        Trigger card learning mode
        
        Args:
            board_id: Board ID or MAC
            timeout: Learning mode timeout in seconds
            
        Returns:
            True if published successfully
        """
        try:
            topic = f"boards/{board_id}/card/learn"
            payload = json.dumps({"timeout": timeout})
            
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Error publishing card learn: {str(e)}")
            return False
    
    def publish_ota_update(self, board_id: str, firmware_url: str, md5: str, version: str) -> bool:
        """
        Trigger OTA firmware update
        
        Args:
            board_id: Board ID or MAC
            firmware_url: Firmware download URL
            md5: MD5 hash for verification
            version: Target version
            
        Returns:
            True if published successfully
        """
        try:
            topic = f"boards/{board_id}/ota"
            payload = json.dumps({
                "url": firmware_url,
                "md5": md5,
                "version": version
            })
            
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Error publishing OTA update: {str(e)}")
            return False


# Global MQTT service instance
mqtt_service = MQTTService()


# Helper functions for easy import
def start_mqtt_service():
    """Start MQTT service"""
    mqtt_service.start()


def stop_mqtt_service():
    """Stop MQTT service"""
    mqtt_service.stop()


def publish_device_control(board_id: str, device_gpio: int, state: dict) -> bool:
    """Publish device control command"""
    return mqtt_service.publish_device_control(board_id, device_gpio, state)


def publish_card_sync(board_id: str, cards: list) -> bool:
    """Publish card sync"""
    return mqtt_service.publish_card_sync(board_id, cards)


def publish_ota_update(board_id: str, firmware_url: str, md5: str, version: str) -> bool:
    """Publish OTA update"""
    return mqtt_service.publish_ota_update(board_id, firmware_url, md5, version)