"""
Pairing Session model
Quản lý phiên pair board vào home.

Lifecycle:
  1. Board giữ nút >= 5s → publish MQTT boards/{mac}/pairing
  2. Server tạo PairingSession với TTL 30 giây
  3. User quét QR (chứa MAC) → gọi POST /boards/pair
  4. Server kiểm tra session còn hạn → pair thành công → xóa session
  5. Session hết hạn mà chưa pair → cleanup service tự xóa
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# Thời gian pairing session tồn tại (giây)
PAIRING_SESSION_TTL = 30


class PairingSession(Base):
    """
    Pairing session model

    Attributes:
        id: UUID primary key
        mac_address: Board MAC address (AA:BB:CC:DD:EE:FF)
        board_type: Loại board (ESP8266_CONTROL_V1, ...)
        firmware_version: Version firmware hiện tại của board
        expires_at: Thời điểm hết hạn (created_at + 30s)
        created_at: Thời điểm tạo session
    """
    __tablename__ = "pairing_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    mac_address = Column(
        String(17),
        nullable=False,
        index=True
    )

    board_type = Column(
        String(50),
        nullable=False
        # 'ESP8266_CONTROL_V1' | 'ESP8266_SENSOR_V1' | 'ESP32_ACCESS_V1'
    )

    firmware_version = Column(
        String(20),
        nullable=True
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ============================================
    # METHODS
    # ============================================

    def __repr__(self):
        return (
            f"<PairingSession("
            f"mac={self.mac_address}, "
            f"type={self.board_type}, "
            f"expires={self.expires_at}"
            f")>"
        )

    def is_expired(self) -> bool:
        """Kiểm tra session đã hết hạn chưa"""
        return datetime.now(timezone.utc) > self.expires_at