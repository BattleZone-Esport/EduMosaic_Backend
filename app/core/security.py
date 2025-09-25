"""
Security utilities for authentication and authorization
Handles JWT tokens, password hashing, and permission checks
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import sentry_sdk
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# HTTP Bearer scheme
security = HTTPBearer()


class SecurityUtils:
    """Security utility functions"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against hashed password"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            if settings.SENTRY_DSN:
                sentry_sdk.capture_exception(e)
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token

        Args:
            data: Data to encode in token
            expires_delta: Token expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "type": "access"})

        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Create JWT refresh token

        Args:
            data: Data to encode in token

        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({"exp": expire, "type": "refresh"})

        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode JWT token

        Args:
            token: JWT token to decode

        Returns:
            Decoded token data

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def generate_random_password(length: int = 12) -> str:
        """
        Generate a random password

        Args:
            length: Length of the password

        Returns:
            Random password string
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        return password

    @staticmethod
    def generate_verification_token() -> str:
        """Generate a random verification token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a password reset token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Validate password strength

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            return (
                False,
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long",
            )

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"

        return True, ""


class TokenData:
    """Token data model"""

    def __init__(self, user_id: int, username: str, email: str, role: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.role = role


def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> TokenData:
    """
    Get current user from JWT token

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        TokenData object with user information

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials

    try:
        payload = SecurityUtils.decode_token(token)

        user_id = payload.get("sub")
        username = payload.get("username")
        email = payload.get("email")
        role = payload.get("role")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(user_id=int(user_id), username=username, email=email, role=role)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_active_user(
    token_data: TokenData = Depends(get_current_user_token), db: Session = Depends(get_db)
):
    """
    Get current active user from database

    Args:
        token_data: Token data from JWT
        db: Database session

    Returns:
        User object from database

    Raises:
        HTTPException: If user not found or inactive
    """
    from app.models.models import User

    user = db.query(User).filter(User.id == token_data.user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return user


def require_role(allowed_roles: list[str]):
    """
    Dependency to require specific user roles

    Args:
        allowed_roles: List of allowed role names

    Returns:
        Dependency function
    """

    def role_checker(current_user=Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return role_checker


def require_admin(current_user=Depends(get_current_active_user)):
    """Dependency to require admin role"""
    if current_user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_super_admin(current_user=Depends(get_current_active_user)):
    """Dependency to require super admin role"""
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required"
        )
    return current_user


class PermissionChecker:
    """Permission checking utility"""

    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions

    def __call__(self, current_user=Depends(get_current_active_user)) -> Any:
        """Check if user has required permissions"""
        # This is a placeholder for permission-based access control
        # You can extend this to check specific permissions from database
        user_permissions = self._get_user_permissions(current_user)

        for permission in self.required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {permission}",
                )

        return current_user

    def _get_user_permissions(self, user) -> list[str]:
        """Get user permissions based on role"""
        # Map roles to permissions
        role_permissions = {
            "SUPER_ADMIN": ["all"],
            "ADMIN": ["manage_users", "manage_content", "view_analytics"],
            "MODERATOR": ["manage_content", "moderate_comments"],
            "CONTENT_CREATOR": ["create_content", "edit_own_content"],
            "PREMIUM_USER": ["access_premium", "no_ads"],
            "USER": ["view_content", "take_quiz"],
            "GUEST": ["view_content"],
        }

        return role_permissions.get(user.role, [])


# Create instances for common permission checks
can_manage_users = PermissionChecker(["manage_users"])
can_manage_content = PermissionChecker(["manage_content"])
can_view_analytics = PermissionChecker(["view_analytics"])
can_create_content = PermissionChecker(["create_content"])
