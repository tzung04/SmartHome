# ============================================
# BOARD TEMPLATES
# ============================================

from app.models.device_model import DeviceType


BOARD_TEMPLATES = {
    "ESP8266_CONTROL_V1": {
        "name": "ESP8266 4-Channel Control",
        "devices": [
            {"type": DeviceType.RELAY, "name": "Thiết bị 1", "gpio": 5},
            {"type": DeviceType.RELAY, "name": "Thiết bị 2", "gpio": 4},
            {"type": DeviceType.RELAY, "name": "Thiết bị 3", "gpio": 14},
            {"type": DeviceType.RELAY, "name": "Thiết bị 4", "gpio": 12},
        ]
    },
    
    "ESP8266_SENSOR_V1": {
        "name": "ESP8266 Sensor Module",
        "devices": [
            {"type": DeviceType.DHT11, "name": "Cảm biến nhiệt độ & độ ẩm", "gpio": 4},
            {"type": DeviceType.PIR, "name": "Cảm biến chuyển động", "gpio": 5},
            {"type": DeviceType.LDR, "name": "Cảm biến ánh sáng", "gpio": None},  # ADC
            {"type": DeviceType.RELAY, "name": "Đèn tự động", "gpio": 14},
        ]
    },
    
    "ESP32_ACCESS_V1": {
        "name": "ESP32-CAM Access Control",
        "devices": [
            {"type": DeviceType.RC522, "name": "Đầu đọc thẻ RFID", "gpio": None},
            {"type": DeviceType.CAMERA, "name": "Camera", "gpio": None},
            {"type": DeviceType.DOOR_LOCK, "name": "Khóa cửa điện", "gpio": 3},
        ]
    }
}