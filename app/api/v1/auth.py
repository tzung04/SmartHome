"""
Authentication API Endpoints
User registration, login, password reset
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp,
    verify_otp as verify_otp_hash
)
from app.core.config import settings
from app.crud import user as crud_user
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    TokenRefresh,
    TokenRefreshResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    UserResponse
)
from app.schemas.user import UserResponse as UserDetailResponse
from app.core.permissions import get_current_user
from app.models.user import User
from app.models.password_reset import PasswordResetOTP
from app.services.email_service import send_otp_email, send_welcome_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================
# REGISTER
# ============================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register new user
    
    - Email must be unique
    - Password validated for strength
    - Sends welcome email
    """
    # Check if email already exists
    existing_user = crud_user.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_pwd = hash_password(user_data.password)
    
    # Create user
    user = crud_user.create_user(
        db,
        user_data,
        hashed_pwd
    )
    
    # Send welcome email
    try:
        send_welcome_email(user.email, user.full_name)
    except Exception as e:
        # Log error but don't fail registration
        pass
    
    return user


# ============================================
# LOGIN
# ============================================

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login user
    
    Returns JWT tokens (access + refresh)
    """
    # Get user by email
    user = crud_user.get_user_by_email(db, credentials.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Create tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user
    )


# ============================================
# REFRESH TOKEN
# ============================================

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    # Decode refresh token
    payload = decode_token(token_data.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify user exists and is active
    user = crud_user.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token({"sub": str(user.id)})
    
    return TokenRefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


# ============================================
# FORGOT PASSWORD
# ============================================

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset OTP
    
    Sends 6-digit OTP to email (valid for 10 minutes)
    """
    # Generate OTP
    otp = generate_otp()
    otp_hashed = hash_otp(otp)
    
    # Set expiration
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.otp_expire_minutes
    )
    
    # Save OTP to database
    db_otp = PasswordResetOTP(
        email=request.email,
        otp_hash=otp_hashed,
        expires_at=expires_at
    )
    db.add(db_otp)
    db.commit()
    
    # Send OTP email
    try:
        send_otp_email(request.email, otp)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email"
        )
    
    return ForgotPasswordResponse(
        email=request.email,
        otp_expires_at=expires_at
    )


# ============================================
# RESET PASSWORD
# ============================================

@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using OTP
    
    Verifies OTP and sets new password
    """
    # Find valid OTP
    otp_record = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == request.email,
        PasswordResetOTP.expires_at > datetime.now(timezone.utc)
    ).order_by(PasswordResetOTP.created_at.desc()).first()
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid OTP found for this email"
        )
    
    # Check max attempts
    if otp_record.attempts >= settings.otp_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum OTP attempts exceeded"
        )
    
    # Verify OTP
    if not verify_otp_hash(request.otp, otp_record.otp_hash):
        otp_record.increment_attempts()
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP. {settings.otp_max_attempts - otp_record.attempts} attempts remaining"
        )
    
    # Get user
    user = crud_user.get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    new_hashed_password = hash_password(request.new_password)
    crud_user.update_user_password(db, user.id, new_hashed_password)
    
    # Delete used OTP
    db.delete(otp_record)
    db.commit()
    
    return ResetPasswordResponse()


# ============================================
# CHANGE PASSWORD (Authenticated)
# ============================================

@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password (requires authentication)
    
    User must provide old password
    """
    # Verify old password
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update to new password
    new_hashed_password = hash_password(request.new_password)
    crud_user.update_user_password(db, current_user.id, new_hashed_password)
    
    return ChangePasswordResponse()


# ============================================
# GET CURRENT USER
# ============================================

@router.get("/me", response_model=UserDetailResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return current_user