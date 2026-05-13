"""
Pairing Session CRUD operations
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.pairing_session_model import PairingSession, PAIRING_SESSION_TTL


def create_pairing_session(
    db: Session,
    mac_address: str,
    board_type: str,
    firmware_version: Optional[str] = None
) -> PairingSession:
    """
    Tạo pairing session mới cho board.

    Xóa session cũ của cùng MAC trước khi tạo mới —
    tránh trường hợp board bấm nút nhiều lần.

    Args:
        db: Database session
        mac_address: Board MAC address
        board_type: Board type identifier
        firmware_version: Firmware version hiện tại

    Returns:
        PairingSession mới được tạo
    """
    # Xóa session cũ của MAC này (nếu có) trước khi tạo mới
    db.query(PairingSession).filter(
        PairingSession.mac_address == mac_address
    ).delete()
    db.commit()

    now = datetime.now(timezone.utc)
    session = PairingSession(
        mac_address=mac_address,
        board_type=board_type,
        firmware_version=firmware_version,
        expires_at=now + timedelta(seconds=PAIRING_SESSION_TTL),
        created_at=now
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_active_session(
    db: Session,
    mac_address: str
) -> Optional[PairingSession]:
    """
    Lấy pairing session còn hạn của board.

    Args:
        db: Database session
        mac_address: Board MAC address

    Returns:
        PairingSession nếu còn hạn, None nếu không có hoặc đã hết hạn
    """
    return db.query(PairingSession).filter(
        PairingSession.mac_address == mac_address,
        PairingSession.expires_at > datetime.now(timezone.utc)
    ).first()


def delete_session(db: Session, mac_address: str) -> None:
    """
    Xóa tất cả pairing sessions của board sau khi pair thành công.

    Args:
        db: Database session
        mac_address: Board MAC address
    """
    db.query(PairingSession).filter(
        PairingSession.mac_address == mac_address
    ).delete()
    db.commit()


def cleanup_expired_sessions(db: Session) -> int:
    """
    Xóa tất cả pairing sessions đã hết hạn.
    Được gọi bởi cleanup_service hàng ngày.

    Args:
        db: Database session

    Returns:
        Số lượng session đã xóa
    """
    deleted = db.query(PairingSession).filter(
        PairingSession.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()
    return deleted