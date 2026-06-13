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
from app.crud import user_crud as crud_user
from app.schemas.auth_schemas import (
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
    UserResponse,
    RegisterInitiateRequest,
    RegisterInitiateResponse,
    RegisterVerifyRequest,
)
from app.models.pending_registration_model import PendingRegistration
from app.schemas.user_schemas import UserResponse as UserDetailResponse
from app.core.permissions import get_current_user
from app.models.user_model import User
from app.models.password_reset_model import PasswordResetOTP
from app.services.email_service import send_otp_email, send_welcome_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================
# REGISTER — GỬI OTP XÁC THỰC EMAIL
# ============================================

@router.post("/register/initiate", response_model=RegisterInitiateResponse)
async def register_initiate(
    user_data: RegisterInitiateRequest,
    db: Session = Depends(get_db)
):
    """
    Gửi OTP xác thực email

    - Kiểm tra email chưa tồn tại trong users
    - Kiểm tra email chưa có pending request (nếu có thì ghi đè record cũ)
    - Hash password, tạo OTP 6 số
    - Lưu vào pending_registrations
    - Gửi OTP qua email
    """
    # Kiểm tra email đã đăng ký chưa
    existing_user = crud_user.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Xóa pending request cũ nếu có (user request lại OTP)
    db.query(PendingRegistration).filter(
        PendingRegistration.email == user_data.email
    ).delete()
    db.commit()

    # Hash password
    hashed_pwd = hash_password(user_data.password)

    # Tạo OTP
    otp = generate_otp()
    otp_hashed = hash_otp(otp)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.otp_expire_minutes
    )

    # Lưu pending registration
    pending = PendingRegistration(
        email=user_data.email,
        hashed_password=hashed_pwd,
        full_name=user_data.full_name,
        otp_hash=otp_hashed,
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()

    # Gửi OTP email
    from app.services.email_service import send_verification_email
    try:
        send_verification_email(user_data.email, otp)
    except Exception:
        # Rollback pending record nếu gửi mail thất bại
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email"
        )

    return RegisterInitiateResponse(
        email=user_data.email,
        otp_expires_at=expires_at,
    )


# ============================================
# REGISTER — XÁC NHẬN OTP, TẠO USER
# ============================================

@router.post("/register/verify", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_verify(
    request: RegisterVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Xác nhận OTP và tạo tài khoản

    - Tìm pending registration theo email (mới nhất, chưa hết hạn)
    - Verify OTP + kiểm tra attempts
    - Tạo user mới với is_verified=True
    - Xóa pending registration
    - Gửi welcome email
    """
    # Tìm pending registration mới nhất còn hạn
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == request.email,
        PendingRegistration.expires_at > datetime.now(timezone.utc)
    ).order_by(PendingRegistration.created_at.desc()).first()

    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid registration request found. Please register again."
        )

    # Kiểm tra số lần nhập sai
    if pending.attempts >= settings.otp_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum OTP attempts exceeded. Please register again."
        )

    # Verify OTP
    if not verify_otp_hash(request.otp, pending.otp_hash):
        pending.increment_attempts()
        db.commit()
        remaining = settings.otp_max_attempts - pending.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP. {remaining} attempts remaining."
        )

    # Double-check email chưa được đăng ký trong lúc chờ OTP
    if crud_user.get_user_by_email(db, request.email):
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Tạo user trực tiếp — is_verified=True ngay vì đã xác thực email
    from app.models.user_model import UserRole
    user = User(
        email=pending.email,
        hashed_password=pending.hashed_password,
        full_name=pending.full_name,
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Xóa pending record
    db.delete(pending)
    db.commit()

    # Gửi welcome email (không fail nếu lỗi)
    try:
        send_welcome_email(user.email, user.full_name)
    except Exception:
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

    Sends 6-digit OTP to email (valid for 10 minutes).
    Always returns the same response regardless of whether email exists
    to prevent email enumeration attacks.
    """
    # Tính expires_at trước để trả response đồng nhất dù email có tồn tại hay không
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.otp_expire_minutes
    )

    # Chỉ tạo OTP và gửi email khi user tồn tại
    user = crud_user.get_user_by_email(db, request.email)
    if user and user.is_active:
        otp = generate_otp()
        otp_hashed = hash_otp(otp)

        db_otp = PasswordResetOTP(
            email=request.email,
            otp_hash=otp_hashed,
            expires_at=expires_at
        )
        db.add(db_otp)
        db.commit()

        try:
            send_otp_email(request.email, otp)
        except Exception:
            # Rollback OTP record nếu gửi mail thất bại
            db.delete(db_otp)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email"
            )

    # Luôn trả cùng 1 response — không tiết lộ email có tồn tại hay không
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

# ============================================
# FCM service
# ============================================

@router.put("/me/fcm-token")
async def update_fcm_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update FCM token for push notifications"""
    user = crud_user.get_user_by_id(db, current_user.id)
    user.fcm_token = token
    user.fcm_updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "FCM token updated"}