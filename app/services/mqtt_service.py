"""
MQTT Service - ALL-IN-ONE
MQTT client with integrated board monitoring and LWT support
"""
import json
import logging
import asyncio
from typing import Optional, Set
from threading import Thread
from datetime import datetime, timedelta, timezone
from uuid import UUID
import paho.mqtt.client as mqtt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import board_crud as crud_board
from app.crud import device_crud as crud_device
from app.crud import access_control_crud as crud_access_control
from app.crud import home_crud as crud_home
from app.services.fcm_service import (
    notify_access_event,
    notify_access_event_to_home_members,
    notify_board_offline,
    notify_board_online,
    notify_board_status_to_home_members
)
from app.services.websocket_manager import manager as ws_manager
from app.services.downsample_service import process_and_save_sensor_data
from app.models.access_control_model import AccessResult
from app.crud import pairing_session_crud as crud_pairing

logger = logging.getLogger(__name__)


class MQTTService:
    """
    All-in-one MQTT service with:
    - MQTT client for board communication
    - LWT (Last Will Testament) support
    - Integrated board monitoring (check every 30s)
    - FCM notifications for all events

    Topic structure:
    - boards/{board_mac}/lwt             - Last Will Testament
    - boards/{board_mac}/status          - Board heartbeat
    - boards/{board_mac}/state           - Device state updates
    - boards/{board_mac}/sensor          - Sensor data
    - boards/{board_mac}/control         - Control commands (from server)
    - boards/{board_mac}/card/learned    - Card learned event
    - boards/{board_mac}/access          - Access log (không còn image_base64)
    - boards/{board_mac}/ota             - OTA commands

    Luồng ảnh access log:
    - MQTT /access chỉ mang metadata (card_uid, result, request_id)
    - Ảnh được gửi riêng qua HTTP POST /api/v1/boards/access/image
    - FCM gửi ngay khi nhận MQTT
    """

    def __init__(self):
        """Initialize MQTT service with board monitoring"""
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Board monitoring
        self.scheduler = AsyncIOScheduler()
        self.online_boards: Set[UUID] = set()
        self.offline_notified: Set[UUID] = set()

    def start(self):
        """Start MQTT service and board monitoring"""
        try:
            # Setup async event loop
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                loop_thread = Thread(target=self._run_async_loop, daemon=True)
                loop_thread.start()

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

            # Start MQTT loop
            self.client.loop_start()

            # Start board monitoring scheduler
            self.scheduler.add_job(
                self._check_board_statuses,
                trigger=IntervalTrigger(seconds=30),
                id='board_status_monitor',
                name='Board Status Monitor',
                replace_existing=True
            )
            self.scheduler.start()

            logger.info("MQTT service started")

        except Exception as e:
            logger.error(f"Error starting MQTT service: {str(e)}")
            raise

    def _run_async_loop(self):
        """Run async event loop in separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        """Stop MQTT service and board monitoring"""
        if self.scheduler.running:
            self.scheduler.shutdown()

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        logger.info("MQTT service stopped")

    def _run_async(self, coro):
        """Schedule coroutine to run in event loop"""
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            logger.warning("Event loop not available")

    # ============================================
    # MQTT CALLBACKS
    # ============================================

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            self._subscribe_topics()
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')

            logger.debug(f"MQTT: {topic} = {payload}")

            # Route to handler
            if '/lwt' in topic:
                self._handle_lwt(topic, payload)
            elif '/pairing' in topic:
                self._handle_pairing_mode(topic, payload)
            elif '/status' in topic:
                self._handle_board_status(topic, payload)
            elif '/state' in topic:
                self._handle_device_state(topic, payload)
            elif '/sensor' in topic:
                self._handle_sensor_data(topic, payload)
            elif '/card/learned' in topic:
                self._handle_card_learned(topic, payload)
            elif '/access' in topic:
                self._handle_access_log(topic, payload)

        except Exception as e:
            logger.error(f"Error handling MQTT message: {str(e)}")

    def _subscribe_topics(self):
        """Subscribe to MQTT topics"""
        topics = [
            ("boards/+/lwt", 0),
            ("boards/+/pairing", 0),
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

    def _handle_pairing_mode(self, topic: str, payload: str):
        """
        Handle pairing mode request từ board.

        Board giữ nút >= 5s → publish topic này → server tạo pairing session 30s.
        Đồng thời tạo/update board record trong DB (upsert).

        Topic: boards/{board_mac}/pairing
        Payload:
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "board_type": "ESP8266_CONTROL_V1",
            "firmware_version": "1.0.0"     
        }
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)

            board_type = data.get('board_type')
            firmware_version = data.get('firmware_version')

            if not board_type:
                logger.warning(f"Pairing request missing board_type from {board_mac}")
                return

            logger.info(f"Pairing mode activated: {board_mac} ({board_type})")

            db = SessionLocal()
            try:
                # Upsert board record — tạo mới nếu chưa có, update firmware nếu đã có
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    board = crud_board.create_board(
                        db,
                        mac_address=board_mac,
                        board_type=board_type,
                        firmware_version=firmware_version
                    )
                    logger.info(f"New board registered via pairing: {board_mac}")
                else:
                    # Cập nhật firmware version nếu có
                    if firmware_version and board.firmware_version != firmware_version:
                        board.firmware_version = firmware_version
                        db.commit()

                # Nếu board đã paired rồi thì không tạo session
                if board.home_id:
                    logger.warning(
                        f"Board {board_mac} already paired to home {board.home_id}, "
                        f"ignoring pairing request"
                    )
                    return

                # Tạo pairing session (xóa session cũ nếu có)
                session = crud_pairing.create_pairing_session(
                    db,
                    mac_address=board_mac,
                    board_type=board_type,
                    firmware_version=firmware_version
                )

                logger.info(
                    f"Pairing session created: {board_mac}, "
                    f"expires at {session.expires_at}"
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling pairing mode: {str(e)}")

    def _handle_lwt(self, topic: str, payload: str):
        """
        Handle Last Will Testament - board disconnected ungracefully.

        LWT chỉ là tín hiệu gợi ý từ MQTT broker khi mất kết nối đột ngột.
        Không force offline ngay vì:
        1. LWT có thể đến muộn hoặc sai timing
        2. Board có thể reconnect ngay sau đó
        3. Scheduler (_check_board_statuses) sẽ detect offline sau timeout

        → Chỉ xóa khỏi online_boards để scheduler xử lý transition nhanh hơn.
        """
        try:
            board_mac = topic.split('/')[1]
            logger.warning(f"LWT received for board {board_mac} — will confirm via scheduler")

            db = SessionLocal()
            try:
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return
                # Xóa khỏi online_boards → scheduler sẽ detect transition
                # ngay trong lần check tiếp theo (tối đa 30s)
                self.online_boards.discard(board.id)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling LWT: {str(e)}")

    def _handle_board_status(self, topic: str, payload: str):
        """
        Handle board heartbeat.

        Chỉ update last_seen và thêm vào online_boards.
        Không notify FCM/WS tại đây — để scheduler xử lý transition.
        Scheduler là nguồn sự thật duy nhất cho online/offline state.
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            status = data.get('status', 'online')

            db = SessionLocal()
            try:
                # Update last_seen
                board = crud_board.update_board_heartbeat(db, board_mac)
                if not board:
                    return

                # Thêm vào online_boards — scheduler sẽ detect OFFLINE→ONLINE
                # transition và gửi notification nếu cần
                self.online_boards.add(board.id)

                # Sync cards khi board access vừa reconnect
                # (detect qua offline_notified — đã được set bởi scheduler)
                if board.home_id and board.id in self.offline_notified:
                    self.offline_notified.discard(board.id)
                    if board.board_type == "ESP32_ACCESS_V1":
                        self._run_async(self._sync_cards_to_board(board))

                logger.debug(f"Heartbeat from {board_mac} — last_seen updated")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling board status: {str(e)}")

    async def _sync_cards_to_board(self, board):
        """Sync active cards tới một board ESP32_ACCESS_V1 cụ thể"""
        try:
            db = SessionLocal()
            try:
                active_cards = crud_access_control.get_home_cards(
                    db, board.home_id, is_active=True
                )
                cards_payload = [
                    {"card_uid": c.card_uid, "owner_name": c.owner_name}
                    for c in active_cards
                ]
                self.publish_card_sync(board.mac_address, cards_payload)
                logger.info(
                    f"Synced {len(cards_payload)} cards to board {board.mac_address}"
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error syncing cards to board: {str(e)}")

    def _handle_device_state(self, topic: str, payload: str):
        """Handle device state update"""
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            device_gpio = data.get('device_gpio')
            new_state = data.get('state', {})

            db = SessionLocal()
            try:
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return

                devices = crud_device.get_board_devices(db, board.id)
                device = next((d for d in devices if d.gpio == device_gpio), None)

                if device:
                    current_state = device.state or {}
                    merged_state = {**current_state, **new_state}
                    
                    crud_device.update_device_state(
                        db, device.id, merged_state, triggered_by=None
                    )

                    if board.home_id:
                        self._run_async(
                            ws_manager.notify_device_state_change(
                                board.home_id, device.id, new_state
                            )
                        )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling device state: {str(e)}")

    def _handle_sensor_data(self, topic: str, payload: str):
        """Handle sensor data"""
        try:
            board_mac = topic.split('/')[1]
            sensor_data = json.loads(payload)

            db = SessionLocal()
            try:
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    return

                devices = crud_device.get_board_devices(db, board.id)
                sensors = [d for d in devices if d.is_sensor()]

                for device in sensors:
                    # WebSocket real-time
                    if board.home_id:
                        self._run_async(
                            ws_manager.notify_sensor_data(
                                board.home_id, device.id, sensor_data
                            )
                        )
                    
                    # Xử lý lưu database định kỳ 10 phút qua Redis
                    process_and_save_sensor_data(device.id, sensor_data, settings.downsample_interval)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling sensor data: {str(e)}")

    def _handle_card_learned(self, topic: str, payload: str):
        """
        Handle card learned event.
        Notify home owner để xác nhận đặt tên và đăng ký thẻ.

        Topic: boards/{board_mac}/card/learned
        Payload: {"card_uid": "AABBCCDD"}
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)
            card_uid = data.get('card_uid')

            if not card_uid:
                logger.warning(f"Card learned event missing card_uid from {board_mac}")
                return

            logger.info(f"Card learned: {board_mac} - {card_uid}")

            db = SessionLocal()
            try:
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board or not board.home_id:
                    return

                home = crud_home.get_home_by_id(db, board.home_id)
                if not home or not home.owner_id:
                    return

                # Notify owner qua WebSocket để app hiển thị popup đăng ký thẻ
                self._run_async(
                    ws_manager.notify_card_learned(
                        board.home_id, board.id, card_uid
                    )
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling card learned: {str(e)}")

    def _handle_access_log(self, topic: str, payload: str):
        """
        Handle access log event từ ESP32-CAM.
        """
        try:
            board_mac = topic.split('/')[1]
            data = json.loads(payload)

            request_id = data.get('request_id')
            card_uid = data.get('card_uid')
            result = data.get('result', 'unknown_card')

            if not request_id:
                logger.warning(f"Access log missing request_id from board {board_mac}")

            if not card_uid:
                logger.warning(f"Access log missing card_uid from board {board_mac}")
                return

            db = SessionLocal()
            try:
                board = crud_board.get_board_by_mac(db, board_mac)
                if not board:
                    logger.warning(f"Unknown board MAC: {board_mac}")
                    return

                # Lookup card để lấy owner_name cho FCM
                card = None
                if card_uid and board.home_id:
                    card = crud_access_control.get_card_by_uid(db, card_uid)

                # Tạo log — image_url=None
                # Ảnh sẽ được update sau khi HTTP endpoint nhận upload từ ESP32
                crud_access_control.create_access_log(
                    db=db,
                    board_id=board.id,
                    card_uid=card_uid,
                    result=AccessResult(result),
                    request_id=request_id,
                    image_url=None,
                )

                logger.info(
                    f"Access log created: board={board_mac}, "
                    f"card={card_uid}, result={result}, request_id={request_id}"
                )

                # WebSocket notify
                if board.home_id:
                    self._run_async(
                        ws_manager.notify_access_log(
                            board.home_id, board.id, card_uid, result,
                            image_url=None
                        )
                    )

                # FCM 
                home = board.home
                if home:
                    board_name = board.name or f"Board {board.mac_address[-8:]}"
                    card_owner = card.owner_name if card else "Unknown"

                    # Owner
                    if home.owner and home.owner.fcm_token:
                        notify_access_event(
                            fcm_token=home.owner.fcm_token,
                            card_owner=card_owner,
                            result=result,
                            board_name=board_name,
                            home_name=home.name,
                            image_url=None
                        )

                    # Members
                    members = crud_home.get_home_members_with_fcm(db, board.home_id)
                    if members:
                        tokens = [m.user.fcm_token for m in members if m.user.fcm_token]
                        if tokens:
                            notify_access_event_to_home_members(
                                fcm_tokens=tokens,
                                card_owner=card_owner,
                                result=result,
                                board_name=board_name,
                                home_name=home.name,
                                image_url=None
                            )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling access log: {str(e)}")

    # ============================================
    # BOARD MONITORING (runs every 30s)
    # ============================================

    async def _check_board_statuses(self):
        """Check all paired boards for offline status"""
        db = SessionLocal()
        try:
            boards = crud_board.get_all_paired_boards(db)
            if not boards:
                return

            now = datetime.now(timezone.utc)
            timeout = now - timedelta(seconds=settings.board_offline_timeout)

            for board in boards:
                try:
                    await self._check_single_board(db, board, timeout)
                except Exception as e:
                    logger.error(f"Error checking board {board.id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in board monitor: {str(e)}")
        finally:
            db.close()

    async def _check_single_board(self, db, board, timeout_threshold):
        """Check single board and handle online/offline transitions"""
        was_online = board.id in self.online_boards
        is_online = (
            board.last_seen is not None and
            board.last_seen > timeout_threshold
        )

        if was_online == is_online:
            return

        # ONLINE -> OFFLINE
        if was_online and not is_online:
            logger.warning(f"Board {board.mac_address} went OFFLINE")

            crud_board.update_board_status(db, board.id, "offline")
            self.online_boards.discard(board.id)

            if board.id not in self.offline_notified:
                await self._send_offline_notifications(board)
                self.offline_notified.add(board.id)

            if board.home_id:
                await ws_manager.notify_board_status_change(
                    board.home_id, board.id, "offline"
                )

        # OFFLINE -> ONLINE
        elif not was_online and is_online:
            logger.info(f"Board {board.mac_address} came ONLINE")

            crud_board.update_board_status(db, board.id, "online")
            self.online_boards.add(board.id)

            # Chỉ gửi notification nếu chưa được gửi bởi _handle_board_status
            if board.id in self.offline_notified:
                await self._send_online_notifications(board)
                self.offline_notified.discard(board.id)  

            if board.home_id:
                await ws_manager.notify_board_status_change(
                    board.home_id, board.id, "online"
                )

    async def _send_offline_notifications(self, board):
        """Send FCM notifications for board offline"""
        try:
            if not board.home_id:
                return

            db = SessionLocal()
            try:
                home = crud_home.get_home_by_id(db, board.home_id)
                if not home:
                    return

                board_name = board.name or f"Board {board.mac_address[-8:]}"

                # Owner
                if home.owner and home.owner.fcm_token:
                    notify_board_offline(
                        home.owner.fcm_token, board_name, str(board.id),
                        home.name, board.last_seen
                    )

                # Members
                members = crud_home.get_home_members_with_fcm(db, board.home_id)
                if members:
                    tokens = [m.user.fcm_token for m in members if m.user.fcm_token]
                    if tokens:
                        notify_board_status_to_home_members(
                            tokens, board_name, str(board.id), False, home.name
                        )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error sending offline notifications: {str(e)}")

    async def _send_online_notifications(self, board):
        """Send FCM notifications for board online"""
        try:
            if not board.home_id:
                return

            db = SessionLocal()
            try:
                home = crud_home.get_home_by_id(db, board.home_id)
                if not home:
                    return

                board_name = board.name or f"Board {board.mac_address[-8:]}"

                # Owner
                if home.owner and home.owner.fcm_token:
                    notify_board_online(
                        home.owner.fcm_token, board_name, str(board.id), home.name
                    )

                # Members
                members = crud_home.get_home_members_with_fcm(db, board.home_id)
                if members:
                    tokens = [m.user.fcm_token for m in members if m.user.fcm_token]
                    if tokens:
                        notify_board_status_to_home_members(
                            tokens, board_name, str(board.id), True, home.name
                        )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error sending online notifications: {str(e)}")

    # ============================================
    # PUBLISH METHODS
    # ============================================

    def publish_device_control(self, board_id: str, device_gpio: int, state: dict) -> bool:
        """Publish device control command"""
        try:
            topic = f"boards/{board_id}/control"
            payload = json.dumps({"device_gpio": device_gpio, "state": state})
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"Error publishing control: {str(e)}")
            return False

    def publish_card_sync(self, board_id: str, cards: list) -> bool:
        """Publish card sync to board"""
        try:
            topic = f"boards/{board_id}/card/sync"
            payload = json.dumps({"cards": cards})
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"Error publishing card sync: {str(e)}")
            return False

    def publish_card_learn(self, board_id: str, timeout: int = 30) -> bool:
        """Trigger card learning mode"""
        try:
            topic = f"boards/{board_id}/card/learn"
            payload = json.dumps({"timeout": timeout})
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"Error publishing card learn: {str(e)}")
            return False

    def publish_ota_update(self, board_id: str, firmware_url: str, md5: str, version: str) -> bool:
        """Trigger OTA firmware update"""
        try:
            topic = f"boards/{board_id}/ota"
            payload = json.dumps({"url": firmware_url, "md5": md5, "version": version})
            result = self.client.publish(topic, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"Error publishing OTA: {str(e)}")
            return False

    def publish_paired(self, board_mac: str, home_id: str, home_name: str) -> bool:
        """
        Notify board rằng đã được pair thành công.
        Board dùng thông tin này để lưu vào LittleFS và đổi trạng thái LED.

        Topic: boards/{mac}/paired
        QoS: 1 — đảm bảo board nhận được
        """
        try:
            topic = f"boards/{board_mac}/paired"
            payload = json.dumps({
                "home_id": home_id,
                "home_name": home_name
            })
            result = self.client.publish(topic, payload, qos=1)
            success = result.rc == mqtt.MQTT_ERR_SUCCESS
            if success:
                logger.info(f"Paired notification sent to board {board_mac}")
            else:
                logger.warning(f"Failed to send paired notification to {board_mac}")
            return success
        except Exception as e:
            logger.error(f"Error publishing paired: {str(e)}")
            return False


# Global instance
mqtt_service = MQTTService()


# Helper functions
def start_mqtt_service():
    """Start MQTT service (includes board monitoring)"""
    mqtt_service.start()


def stop_mqtt_service():
    """Stop MQTT service"""
    mqtt_service.stop()


def publish_device_control(board_id: str, device_gpio: int, state: dict) -> bool:
    return mqtt_service.publish_device_control(board_id, device_gpio, state)


def publish_card_sync(board_id: str, cards: list) -> bool:
    return mqtt_service.publish_card_sync(board_id, cards)


def publish_ota_update(board_id: str, firmware_url: str, md5: str, version: str) -> bool:
    return mqtt_service.publish_ota_update(board_id, firmware_url, md5, version)


def publish_paired(board_mac: str, home_id: str, home_name: str) -> bool:
    return mqtt_service.publish_paired(board_mac, home_id, home_name)