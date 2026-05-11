"""
Home CRUD operations
Database queries for home and member management
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.home_model import Home, HomeMember, MemberRole
from app.models.floor_model import Floor, Room
from app.models.user_model import User
from app.schemas.home_schemas import HomeCreate, HomeUpdate, FloorCreate, RoomCreate, RoomUpdate


# ============================================
# HOME - CREATE
# ============================================

def create_home(db: Session, home: HomeCreate, owner_id: UUID) -> Home:
    """
    Create new home
    
    Args:
        db: Database session
        home: Home creation data
        owner_id: Owner user UUID
        
    Returns:
        Created home
    """
    db_home = Home(
        name=home.name,
        address=home.address,
        owner_id=owner_id
    )
    db.add(db_home)
    db.commit()
    db.refresh(db_home)
    
    # Create owner membership
    create_member(db, db_home.id, owner_id, MemberRole.OWNER)
    
    return db_home


# ============================================
# HOME - READ
# ============================================

def get_home_by_id(db: Session, home_id: UUID) -> Optional[Home]:
    """Get home by ID"""
    return db.query(Home).filter(Home.id == home_id).first()


def get_user_homes(db: Session, user_id: UUID) -> list[tuple[Home, MemberRole]]:
    """
    Get all homes where user is a member
    
    Returns:
        List of (Home, MemberRole) tuples
    """
    results = db.query(Home, HomeMember.role).join(
        HomeMember,
        Home.id == HomeMember.home_id
    ).filter(
        HomeMember.user_id == user_id
    ).order_by(Home.created_at.desc()).all()
    
    return results


def get_all_homes(db: Session, skip: int = 0, limit: int = 50) -> tuple[list[Home], int]:
    """
    Get all homes (admin only)
    
    Returns:
        Tuple of (homes list, total count)
    """
    query = db.query(Home)
    total = query.count()
    homes = query.order_by(Home.created_at.desc()).offset(skip).limit(limit).all()
    return homes, total

def get_home_members_with_fcm(db: Session, home_id: UUID) -> List[HomeMember]:
    """Get home members with FCM tokens"""
    return (
        db.query(HomeMember)
        .join(User)
        .filter(
            HomeMember.home_id == home_id,
            User.fcm_token.isnot(None),
            User.is_active == True
        )
        .all()
    )

# ============================================
# HOME - UPDATE
# ============================================

def update_home(db: Session, home_id: UUID, home_update: HomeUpdate) -> Optional[Home]:
    """Update home information"""
    db_home = get_home_by_id(db, home_id)
    if not db_home:
        return None
    
    if home_update.name is not None:
        db_home.name = home_update.name
    
    if home_update.address is not None:
        db_home.address = home_update.address
    
    db.commit()
    db.refresh(db_home)
    return db_home


# ============================================
# HOME - DELETE
# ============================================

def delete_home(db: Session, home_id: UUID) -> bool:
    """Delete home (cascade deletes all related data)"""
    db_home = get_home_by_id(db, home_id)
    if not db_home:
        return False
    
    db.delete(db_home)
    db.commit()
    return True


# ============================================
# MEMBER - CREATE
# ============================================

def create_member(db: Session, home_id: UUID, user_id: UUID, role: MemberRole) -> HomeMember:
    """Add member to home"""
    db_member = HomeMember(
        home_id=home_id,
        user_id=user_id,
        role=role
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member


# ============================================
# MEMBER - READ
# ============================================

def get_member(db: Session, home_id: UUID, user_id: UUID) -> Optional[HomeMember]:
    """Get specific member"""
    return db.query(HomeMember).filter(
        HomeMember.home_id == home_id,
        HomeMember.user_id == user_id
    ).first()


def get_home_members(db: Session, home_id: UUID) -> list[HomeMember]:
    """Get all members of a home"""
    return db.query(HomeMember).filter(
        HomeMember.home_id == home_id
    ).order_by(HomeMember.added_at).all()


def is_home_owner(db: Session, home_id: UUID, user_id: UUID) -> bool:
    """Check if user is owner of home"""
    member = get_member(db, home_id, user_id)
    return member is not None and member.role == MemberRole.OWNER


def is_home_member(db: Session, home_id: UUID, user_id: UUID) -> bool:
    """Check if user is member of home (any role)"""
    return get_member(db, home_id, user_id) is not None


# ============================================
# MEMBER - UPDATE
# ============================================

def update_member_role(db: Session, home_id: UUID, user_id: UUID, new_role: MemberRole) -> Optional[HomeMember]:
    """Update member role (for ownership transfer)"""
    member = get_member(db, home_id, user_id)
    if not member:
        return None
    
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def transfer_ownership(db: Session, home_id: UUID, current_owner_id: UUID, new_owner_id: UUID) -> bool:
    """
    Transfer home ownership
    
    Args:
        db: Database session
        home_id: Home UUID
        current_owner_id: Current owner UUID
        new_owner_id: New owner UUID
        
    Returns:
        True if successful, False otherwise
    """
    # Verify current owner
    current_owner = get_member(db, home_id, current_owner_id)
    if not current_owner or current_owner.role != MemberRole.OWNER:
        return False
    
    # Verify new owner is a member
    new_owner = get_member(db, home_id, new_owner_id)
    if not new_owner:
        return False
    
    # Demote current owner to member
    current_owner.role = MemberRole.MEMBER
    
    # Promote new owner
    new_owner.role = MemberRole.OWNER
    
    # Update home owner_id
    db_home = get_home_by_id(db, home_id)
    if db_home:
        db_home.owner_id = new_owner_id
    
    db.commit()
    return True


# ============================================
# MEMBER - DELETE
# ============================================

def remove_member(db: Session, home_id: UUID, user_id: UUID) -> bool:
    """Remove member from home"""
    member = get_member(db, home_id, user_id)
    if not member:
        return False
    
    db.delete(member)
    db.commit()
    return True


# ============================================
# FLOOR - CRUD
# ============================================

def create_floor(db: Session, home_id: UUID, floor: FloorCreate) -> Floor:
    """Create floor"""
    db_floor = Floor(
        home_id=home_id,
        name=floor.name,
        floor_number=floor.floor_number
    )
    db.add(db_floor)
    db.commit()
    db.refresh(db_floor)
    return db_floor


def get_floor_by_id(db: Session, floor_id: UUID) -> Optional[Floor]:
    """Get floor by ID"""
    return db.query(Floor).filter(Floor.id == floor_id).first()


def get_home_floors(db: Session, home_id: UUID) -> list[Floor]:
    """Get all floors of a home"""
    return db.query(Floor).filter(
        Floor.home_id == home_id
    ).order_by(Floor.floor_number).all()


def delete_floor(db: Session, floor_id: UUID) -> bool:
    """Delete floor"""
    db_floor = get_floor_by_id(db, floor_id)
    if not db_floor:
        return False
    
    db.delete(db_floor)
    db.commit()
    return True


# ============================================
# ROOM - CRUD
# ============================================

def create_room(db: Session, floor_id: UUID, room: RoomCreate) -> Room:
    """Create room"""
    db_room = Room(
        floor_id=floor_id,
        name=room.name,
        template_type=room.template_type,
        position_x=room.position_x,
        position_y=room.position_y,
        width=room.width,
        height=room.height
    )
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room


def get_room_by_id(db: Session, room_id: UUID) -> Optional[Room]:
    """Get room by ID"""
    return db.query(Room).filter(Room.id == room_id).first()


def get_floor_rooms(db: Session, floor_id: UUID) -> list[Room]:
    """Get all rooms on a floor"""
    return db.query(Room).filter(
        Room.floor_id == floor_id
    ).order_by(Room.created_at).all()


def update_room(db: Session, room_id: UUID, room_update: RoomUpdate) -> Optional[Room]:
    """Update room"""
    db_room = get_room_by_id(db, room_id)
    if not db_room:
        return None
    
    if room_update.name is not None:
        db_room.name = room_update.name
    
    if room_update.position_x is not None:
        db_room.position_x = room_update.position_x
    
    if room_update.position_y is not None:
        db_room.position_y = room_update.position_y
    
    if room_update.width is not None:
        db_room.width = room_update.width
    
    if room_update.height is not None:
        db_room.height = room_update.height
    
    db.commit()
    db.refresh(db_room)
    return db_room


def delete_room(db: Session, room_id: UUID) -> bool:
    """Delete room"""
    db_room = get_room_by_id(db, room_id)
    if not db_room:
        return False
    
    db.delete(db_room)
    db.commit()
    return True


# ============================================
# STATISTICS
# ============================================

def count_homes(db: Session) -> int:
    """Get total number of homes"""
    return db.query(func.count(Home.id)).scalar()


def count_home_members(db: Session, home_id: UUID) -> int:
    """Get number of members in a home"""
    return db.query(func.count(HomeMember.id)).filter(
        HomeMember.home_id == home_id
    ).scalar()