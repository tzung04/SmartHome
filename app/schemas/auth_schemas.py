"""
Authentication Pydantic schemas
Request and response models for auth endpoints
"""
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


# ============================================
# USER INFO
# ============================================

class UserResponse(BaseModel):
    """User information response"""
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str  # 'super_admin' or 'user'
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

# ============================================
# REGISTER
# ============================================

class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength:
        - Min 8 characters
        - At least 1 uppercase
        """
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class UserRegisterResponse(BaseModel):
    """User registration response"""
    user: UserResponse
    message: str = "Registration successful. Please verify your email."
    
    model_config = {"from_attributes": True}


# ============================================
# REGISTER — 2-STEP (OTP EMAIL VERIFY)
# ============================================

class RegisterInitiateRequest(BaseModel):
    """Bước 1: Gửi yêu cầu đăng ký, server gửi OTP về email"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class RegisterInitiateResponse(BaseModel):
    """Response bước 1: thông báo OTP đã gửi"""
    email: str
    otp_expires_at: datetime
    message: str = "OTP sent to your email. Valid for 10 minutes."


class RegisterVerifyRequest(BaseModel):
    """Bước 2: Xác nhận OTP để hoàn tất đăng ký"""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')


# ============================================
# LOGIN
# ============================================

class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


# ============================================
# TOKEN REFRESH
# ============================================

class TokenRefresh(BaseModel):
    """Token refresh request"""
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """Token refresh response"""
    access_token: str
    expires_in: int  # seconds


# ============================================
# PASSWORD RESET
# ============================================

class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Forgot password response"""
    email: str
    otp_expires_at: datetime
    message: str = "OTP sent to your email. Valid for 10 minutes."


class ResetPasswordRequest(BaseModel):
    """Reset password with OTP request"""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength (same as registration)"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class ResetPasswordResponse(BaseModel):
    """Reset password response"""
    message: str = "Password reset successfully. Please login with new password."


# ============================================
# CHANGE PASSWORD (Authenticated)
# ============================================

class ChangePasswordRequest(BaseModel):
    """Change password request (requires authentication)"""
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class ChangePasswordResponse(BaseModel):
    """Change password response"""
    message: str = "Password changed successfully"

# ============================================
# STANDARD API RESPONSE
# ============================================

class AuthSuccessResponse(BaseModel):
    """Standard success response for auth endpoints"""
    success: bool = True
    data: Optional[dict] = None
    message: Optional[str] = None


class AuthErrorResponse(BaseModel):
    """Standard error response for auth endpoints"""
    success: bool = False
    data: None = None
    message: str
    error_code: Optional[str] = None