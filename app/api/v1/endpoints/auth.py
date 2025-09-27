"""
Authentication endpoints
Handles user registration, login, password reset, etc.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.cache import cache_manager, cached
from app.core.database import get_db
from app.core.exceptions import AuthenticationException, ValidationException
from app.core.security import SecurityUtils, get_current_active_user
from app.core.config import settings
from app.models import User
from app.schemas.auth import (
    EmailVerification,
    PasswordReset,
    PasswordResetRequest,
    Token,
    TokenRefresh,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth import AuthService
from app.services.email import EmailService
from app.utils.validators import validate_email, validate_password

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Register a new user

    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Strong password (min 8 characters)
    - **full_name**: User's full name
    """
    # Validate email
    if not validate_email(user_data.email):
        raise ValidationException("Invalid email address")

    # Validate password strength
    is_valid, error_msg = SecurityUtils.validate_password_strength(user_data.password)
    if not is_valid:
        raise ValidationException(error_msg)

    # Check if user exists
    if AuthService.get_user_by_email(db, user_data.email):
        raise ValidationException("Email already registered")

    if AuthService.get_user_by_username(db, user_data.username):
        raise ValidationException("Username already taken")

    # Create user
    user = AuthService.create_user(db, user_data)

    # Send verification email in background
    if EmailService.is_configured():
        background_tasks.add_task(
            EmailService.send_verification_email,
            user.email,
            user.full_name,
            user.verification_token,
        )

    return user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login with username/email and password

    Returns access and refresh tokens
    """
    # Authenticate user
    user = AuthService.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise AuthenticationException("Invalid credentials")

    if not user.is_active:
        raise AuthenticationException("Account is inactive")

    # Generate tokens
    access_token = SecurityUtils.create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
        }
    )

    refresh_token = SecurityUtils.create_refresh_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Update last login
    AuthService.update_last_login(db, user.id)

    # Cache user session
    await cache_manager.set(
        f"user_session:{user.id}",
        {
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "last_login": datetime.utcnow().isoformat(),
        },
        expire=86400,  # 24 hours
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token
    """
    try:
        payload = SecurityUtils.decode_token(token_data.refresh_token)

        if payload.get("type") != "refresh":
            raise AuthenticationException("Invalid refresh token")

        user_id = payload.get("sub")
        user = AuthService.get_user_by_id(db, int(user_id))

        if not user:
            raise AuthenticationException("User not found")

        # Generate new access token
        access_token = SecurityUtils.create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": token_data.refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    except Exception as e:
        raise AuthenticationException("Invalid refresh token")


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    Logout current user
    Invalidates cached session
    """
    # Clear cached session
    await cache_manager.delete(f"user_session:{current_user.id}")

    return {"message": "Logged out successfully"}


@router.post("/password/reset-request")
async def request_password_reset(
    request_data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request password reset link
    Sends reset link to user's email
    """
    user = AuthService.get_user_by_email(db, request_data.email)

    if user:
        # Generate reset token
        reset_token = SecurityUtils.generate_reset_token()

        # Save reset token
        AuthService.save_reset_token(db, user.id, reset_token)

        # Send reset email in background
        if EmailService.is_configured():
            background_tasks.add_task(
                EmailService.send_password_reset_email, user.email, user.full_name, reset_token
            )

    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password/reset")
async def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)):
    """
    Reset password using reset token
    """
    # Validate new password
    is_valid, error_msg = SecurityUtils.validate_password_strength(reset_data.new_password)
    if not is_valid:
        raise ValidationException(error_msg)

    # Reset password
    success = AuthService.reset_password(db, reset_data.token, reset_data.new_password)

    if not success:
        raise AuthenticationException("Invalid or expired reset token")

    return {"message": "Password reset successfully"}


@router.post("/verify-email")
async def verify_email(verification: EmailVerification, db: Session = Depends(get_db)):
    """
    Verify email address using verification token
    """
    success = AuthService.verify_email(db, verification.token)

    if not success:
        raise AuthenticationException("Invalid or expired verification token")

    return {"message": "Email verified successfully"}


@router.get("/me", response_model=UserResponse)
@cached(expire=300, key_prefix="user_profile")
async def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """
    Get current user profile
    """
    return current_user


@router.put("/me")
async def update_profile(
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update current user profile
    """
    # Update user profile
    updated_user = AuthService.update_user_profile(db, current_user.id, update_data)

    # Invalidate cache
    await cache_manager.delete(f"user_profile:{current_user.id}")

    return updated_user


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Change password for current user
    """
    # Verify old password
    if not SecurityUtils.verify_password(old_password, current_user.password_hash):
        raise AuthenticationException("Incorrect current password")

    # Validate new password
    is_valid, error_msg = SecurityUtils.validate_password_strength(new_password)
    if not is_valid:
        raise ValidationException(error_msg)

    # Update password
    AuthService.change_password(db, current_user.id, new_password)

    return {"message": "Password changed successfully"}
