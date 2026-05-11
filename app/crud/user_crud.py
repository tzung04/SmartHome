"""
User CRUD operations
Database queries for user management
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user_model import User, UserRole
from app.schemas.user_schemas import UserCreate, UserUpdate
from app.core.security import hash_password


# ============================================
# CREATE
# ============================================

def create_user(db: Session, user: UserCreate, hashed_password: str) -> User:
    """
    Create new user
    
    Args:
        db: Database session
        user: User creation data
        hashed_password: Pre-hashed password
        
    Returns:
        Created user
    """
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=UserRole(user.role) if hasattr(user, 'role') else UserRole.USER
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================
# READ
# ============================================

def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    is_active: Optional[bool] = None,
    role: Optional[UserRole] = None
) -> tuple[list[User], int]:
    """
    Get paginated users list
    
    Args:
        db: Database session
        skip: Offset
        limit: Max results
        is_active: Filter by active status
        role: Filter by role
        
    Returns:
        Tuple of (users list, total count)
    """
    query = db.query(User)
    
    # Apply filters
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if role is not None:
        query = query.filter(User.role == role)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    return users, total


# ============================================
# UPDATE
# ============================================

def update_user(db: Session, user_id: UUID, user_update: UserUpdate) -> Optional[User]:
    """
    Update user information
    
    Args:
        db: Database session
        user_id: User UUID
        user_update: Update data
        
    Returns:
        Updated user or None if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    # Update fields
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    
    if user_update.email is not None:
        db_user.email = user_update.email
    
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_password(db: Session, user_id: UUID, new_hashed_password: str) -> Optional[User]:
    """
    Update user password
    
    Args:
        db: Database session
        user_id: User UUID
        new_hashed_password: New hashed password
        
    Returns:
        Updated user or None if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.hashed_password = new_hashed_password
    db.commit()
    db.refresh(db_user)
    return db_user


def verify_user_email(db: Session, user_id: UUID) -> Optional[User]:
    """
    Mark user email as verified
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Updated user or None if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.is_verified = True
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================
# DELETE / BAN
# ============================================

def ban_user(db: Session, user_id: UUID) -> Optional[User]:
    """
    Ban user (set is_active = False)
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Updated user or None if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.is_active = False
    db.commit()
    db.refresh(db_user)
    return db_user


def unban_user(db: Session, user_id: UUID) -> Optional[User]:
    """
    Unban user (set is_active = True)
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Updated user or None if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.is_active = True
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: UUID) -> bool:
    """
    Permanently delete user (use with caution!)
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        True if deleted, False if not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return False
    
    db.delete(db_user)
    db.commit()
    return True


# ============================================
# SEARCH
# ============================================

def search_users(db: Session, query: str, limit: int = 10) -> list[User]:
    """
    Search users by email or name
    
    Args:
        db: Database session
        query: Search query
        limit: Max results
        
    Returns:
        List of matching users
    """
    search_pattern = f"%{query}%"
    
    return db.query(User).filter(
        (User.email.ilike(search_pattern)) |
        (User.full_name.ilike(search_pattern))
    ).limit(limit).all()


# ============================================
# STATISTICS
# ============================================

def count_users(db: Session) -> int:
    """Get total number of users"""
    return db.query(func.count(User.id)).scalar()


def count_active_users(db: Session) -> int:
    """Get number of active users"""
    return db.query(func.count(User.id)).filter(User.is_active == True).scalar()


def count_super_admins(db: Session) -> int:
    """Get number of super admins"""
    return db.query(func.count(User.id)).filter(User.role == UserRole.SUPER_ADMIN).scalar()