"""
Pending Registration model
Lưu thông tin đăng ký tạm thời trong khi chờ xác thực OTP email
Record tự xóa sau khi verify thành công hoặc cleanup hàng ngày
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PendingRegistration(Base):
    """
    Pending registration model

    Lưu thông tin đăng ký tạm:
    - email, hashed_password, full_name
    - OTP hash để verify
    - Hết hạn sau 10 phút (giống forgot password)

    Attributes:
        id: UUID primary key
        email: Email đăng ký (unique per pending request)
        hashed_password: Mật khẩu đã hash (bcrypt)
        full_name: Họ tên người dùng
        otp_hash: SHA256 hash của OTP 6 số
        expires_at: Thời điểm hết hạn OTP
        attempts: Số lần nhập OTP sai
        created_at: Thời điểm tạo
    """
    __tablename__ = "pending_registrations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email = Column(
        String(255),
        nullable=False,
        index=True
    )

    hashed_password = Column(
        String(255),
        nullable=False
    )

    full_name = Column(
        String(255),
        nullable=False
    )

    otp_hash = Column(
        String(255),
        nullable=False
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    attempts = Column(
        Integer,
        default=0,
        nullable=False
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
        return f"<PendingRegistration(email={self.email}, expires_at={self.expires_at})>"

    def is_expired(self) -> bool:
        """Check if OTP đã hết hạn"""
        return datetime.now(timezone.utc) > self.expires_at

    def increment_attempts(self):
        """Tăng số lần nhập sai"""
        self.attempts += 1