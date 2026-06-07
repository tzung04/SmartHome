"""
Services Module
Background workers and external integrations
"""

# Email service
from app.services.email_service import (
    email_service,
    send_otp_email,
    send_verification_email,
    send_welcome_email,
)

# Storage service
from app.services.storage_service import (
    storage_service,
    upload_firmware,
    delete_firmware,
    upload_access_log_image,
    delete_access_log_image,
)

# Board service
from app.services.board_service import (
    board_service,
    create_devices_for_board,
    is_valid_board_type,
    get_board_info,
    get_all_board_types,
)

# WebSocket manager
from app.services.websocket_manager import (
    manager as ws_manager,
    connect as ws_connect,
    disconnect as ws_disconnect,
    notify_device_state_change,
    notify_board_status_change,
    notify_sensor_data,
    notify_access_log,
)

# MQTT service
from app.services.mqtt_service import (
    mqtt_service,
    start_mqtt_service,
    stop_mqtt_service,
    publish_device_control,
    publish_card_sync,
    publish_ota_update,
)

# Timer service
from app.services.timer_service import (
    timer_service,
    start_timer_service,
    stop_timer_service,
)

# Cleanup service
from app.services.cleanup_service import (
    cleanup_service,
    start_cleanup_service,
    stop_cleanup_service,
    run_manual_cleanup,
)

# Downsample service
from app.services.downsample_service import (
    downsample_service,
)

__all__ = [
    # Email
    "email_service",
    "send_otp_email",
    "send_verification_email",
    "send_welcome_email",
    
    # Storage
    "storage_service",
    "upload_firmware",
    "delete_firmware",
    "upload_access_log_image",
    "delete_access_log_image",
    
    # Board
    "board_service",
    "create_devices_for_board",
    "is_valid_board_type",
    "get_board_info",
    "get_all_board_types",
    
    # WebSocket
    "ws_manager",
    "ws_connect",
    "ws_disconnect",
    "notify_device_state_change",
    "notify_board_status_change",
    "notify_sensor_data",
    "notify_access_log",
    
    # MQTT
    "mqtt_service",
    "start_mqtt_service",
    "stop_mqtt_service",
    "publish_device_control",
    "publish_card_sync",
    "publish_ota_update",
    
    # Timer
    "timer_service",
    "start_timer_service",
    "stop_timer_service",
    
    # Cleanup
    "cleanup_service",
    "start_cleanup_service",
    "stop_cleanup_service",
    "run_manual_cleanup",
    
    # Downsample
    "downsample_service",
]