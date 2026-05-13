"""
Access control models
RFID card management and access logging
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AccessResult(str, enum.Enum):
    """Access result enumeration"""
    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN_CARD = "unknown_card"


class AccessCard(Base):
    """
    Access card model
    
    Manages RFID cards for access control
    
    Attributes:
        id: Unique identifier (UUID)
        home_id: Home UUID
        card_uid: RFID card UID (hexadecimal)
        owner_name: Card owner name
        owner_user_id: User UUID (nullable)
        is_active: Card active status
        valid_from: Valid from timestamp
        valid_until: Valid until timestamp (nullable = permanent)
        created_at: Card creation timestamp
    
    Relationships:
        home: Home this card belongs to
        owner_user: User who owns this card (optional)
        access_logs: Access logs using this card
    """
    __tablename__ = "access_cards"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    home_id = Column(
        UUID(as_uuid=True),
        ForeignKey("homes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    card_uid = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
        # RFID UID in hex (e.g., "AABBCCDD")
    )
    
    owner_name = Column(
        String(255),
        nullable=False
        # Human-readable owner name
    )
    
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
        # Optional link to user account
    )
    
    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )
    
    valid_from = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    valid_until = Column(
        DateTime(timezone=True)
        # NULL = permanent validity
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    home = relationship("Home", back_populates="access_cards")
    owner_user = relationship("User")
    
    access_logs = relationship(
        "AccessLog",
        back_populates="card"
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<AccessCard(id={self.id}, uid={self.card_uid}, owner={self.owner_name})>"
    
    def is_valid(self) -> bool:
        """Check if card is currently valid"""
        now = datetime.now(timezone.utc)
        
        if not self.is_active:
            return False
        
        if now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        return True


class AccessLog(Base):
    """
    Access log model
    
    Records all RFID card scan attempts with photos.
    Retention: 7 days (with automatic image cleanup)
    
    Luồng tạo log (2 bước):
      1. MQTT /access  → tạo log với image_url=null, lưu request_id
      2. HTTP POST /boards/access/image → upload ảnh, update image_url → gửi FCM
    
    Attributes:
        id: Unique identifier (UUID)
        board_id: Board UUID (ESP32-CAM)
        card_uid: Scanned card UID
        card_id: AccessCard UUID (nullable for unknown cards)
        result: Access result (granted/denied/unknown_card)
        request_id: UUID do ESP32 sinh, dùng để ghép MQTT event với HTTP image upload
        image_url: Supabase Storage URL for photo (null cho đến khi HTTP image upload xong)
        created_at: Scan timestamp
    
    Relationships:
        board: Board that scanned the card
        card: AccessCard (if known)
        home: Home (via board)
    """
    __tablename__ = "access_logs"
    
    # ============================================
    # COLUMNS
    # ============================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    board_id = Column(
        UUID(as_uuid=True),
        ForeignKey("boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    card_uid = Column(
        String(20),
        nullable=False
        # RFID UID that was scanned
    )
    
    card_id = Column(
        UUID(as_uuid=True),
        ForeignKey("access_cards.id", ondelete="SET NULL"),
        nullable=True
        # NULL = unknown card
    )
    
    result = Column(
        SQLEnum(AccessResult, name='access_result'),
        nullable=False
    )

    request_id = Column(
        String(36),
        nullable=True,  
        index=True,
        unique=True
    )
    
    image_url = Column(
        Text,
        nullable=True
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    board = relationship("Board", back_populates="access_logs")
    card = relationship("AccessCard", back_populates="access_logs")
    
    # For convenience - access home via board.home
    @property
    def home(self):
        """Get home this access log belongs to"""
        return self.board.home if self.board else None
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<AccessLog(id={self.id}, card_uid={self.card_uid}, result={self.result}, at={self.created_at})>"
    
    def was_granted(self) -> bool:
        """Check if access was granted"""
        return self.result == AccessResult.GRANTED

    def has_image(self) -> bool:
        """Check if image has been uploaded"""
        return self.image_url is not None