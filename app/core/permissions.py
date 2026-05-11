"""
Authorization and permissions management
Role-based access control (RBAC) decorators
"""
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token


# ============================================
# SECURITY SCHEME
# ============================================

security = HTTPBearer()


# ============================================
# AUTHENTICATION
# ============================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials with JWT token
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    # Import here to avoid circular imports
    from app.models.user_model import User, UserRole
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Extract token from credentials
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    # Verify token type
    if payload.get("type") != "access":
        raise credentials_exception
    
    # Get user ID from payload
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Query user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


# ============================================
# SYSTEM-LEVEL AUTHORIZATION
# ============================================

def require_super_admin(
    current_user = Depends(get_current_user)
):
    """
    Require super admin role for system-level operations
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User object if super admin
        
    Raises:
        HTTPException 403: If user is not super admin
    """
    # Import here to avoid circular imports
    from app.models.user_model import UserRole
    
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user


# ============================================
# HOME-LEVEL AUTHORIZATION
# ============================================

def require_home_access(
    home_id: UUID,
    required_role = None,  # Will be MemberRole.MEMBER by default
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Check if user has access to home with required role
    
    Args:
        home_id: UUID of the home
        required_role: Minimum required role (owner > member)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        HomeMember object if authorized, None if super admin
        
    Raises:
        HTTPException 403: If not authorized
    """
    # Import here to avoid circular imports
    from app.models.user_model import UserRole
    from app.models.home_model import HomeMember, MemberRole
    
    # Default required role
    if required_role is None:
        required_role = MemberRole.MEMBER
    
    # Super admin has access to all homes
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    
    # Check membership
    membership = db.query(HomeMember).filter(
        HomeMember.home_id == home_id,
        HomeMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home"
        )
    
    # Check role hierarchy
    role_hierarchy = {
        MemberRole.OWNER: 2,
        MemberRole.MEMBER: 1
    }
    
    if role_hierarchy[membership.role] < role_hierarchy[required_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires {required_role.value} role"
        )
    
    return membership


def require_home_owner(
    home_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Shorthand for require_home_access with owner role
    
    Args:
        home_id: UUID of the home
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        HomeMember object if owner, None if super admin
    """
    # Import here to avoid circular imports
    from app.models.home_model import MemberRole
    
    return require_home_access(home_id, MemberRole.OWNER, db, current_user)


# ============================================
# RESOURCE-LEVEL AUTHORIZATION
# ============================================

def require_resource_access(
    resource_type: str,
    resource_id: UUID,
    required_role = None,  # Will be MemberRole.MEMBER by default
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Check if user has access to a resource (board, device, etc.)
    by checking their membership in the resource's home
    
    Args:
        resource_type: 'board', 'device', 'timer', etc.
        resource_id: UUID of the resource
        required_role: Minimum required role
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        HomeMember object if authorized, None if super admin
        
    Raises:
        HTTPException 403: If not authorized
        HTTPException 404: If resource not found
    """
    # Import models here to avoid circular imports
    from app.models.user_model import UserRole
    from app.models.home_model import MemberRole
    from app.models.board_model import Board
    from app.models.device_model import Device
    from app.models.timer_model import Timer
    
    # Default required role
    if required_role is None:
        required_role = MemberRole.MEMBER
    
    # Super admin has access to all resources
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    
    # Get home_id from resource
    home_id = None
    
    if resource_type == 'board':
        board = db.query(Board).filter(Board.id == resource_id).first()
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found"
            )
        home_id = board.home_id
        
    elif resource_type == 'device':
        device = db.query(Device).join(Board).filter(
            Device.id == resource_id
        ).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        home_id = device.board.home_id
        
    elif resource_type == 'timer':
        timer = db.query(Timer).join(Device).join(Board).filter(
            Timer.id == resource_id
        ).first()
        if not timer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timer not found"
            )
        home_id = timer.device.board.home_id
    
    else:
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    if not home_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type.capitalize()} has no associated home"
        )
    
    return require_home_access(home_id, required_role, db, current_user)


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_home_owner(
    user_id: UUID,
    home_id: UUID,
    db: Session
) -> bool:
    """
    Check if user is owner of home
    
    Args:
        user_id: User UUID
        home_id: Home UUID
        db: Database session
        
    Returns:
        True if user is owner, False otherwise
    """
    # Import here to avoid circular imports
    from app.models.home_model import HomeMember, MemberRole
    
    membership = db.query(HomeMember).filter(
        HomeMember.home_id == home_id,
        HomeMember.user_id == user_id,
        HomeMember.role == MemberRole.OWNER
    ).first()
    
    return membership is not None


def is_home_member(
    user_id: UUID,
    home_id: UUID,
    db: Session
) -> bool:
    """
    Check if user is member of home (any role)
    
    Args:
        user_id: User UUID
        home_id: Home UUID
        db: Database session
        
    Returns:
        True if user is member, False otherwise
    """
    # Import here to avoid circular imports
    from app.models.home_model import HomeMember
    
    membership = db.query(HomeMember).filter(
        HomeMember.home_id == home_id,
        HomeMember.user_id == user_id
    ).first()
    
    return membership is not None