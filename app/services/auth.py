"""Authentication service"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import SecurityUtils
from app.models import User


class AuthService:
    @staticmethod
    def create_user(db: Session, user_data) -> User:
        """Create a new user"""
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=SecurityUtils.get_password_hash(user_data.password),
            full_name=user_data.full_name,
            verification_token=SecurityUtils.generate_verification_token(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user by username or email"""
        user = db.query(User).filter((User.username == username) | (User.email == username)).first()

        if user and SecurityUtils.verify_password(password, user.password_hash):
            return user
        return None

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_last_login(db: Session, user_id: int):
        """Update user's last login time"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.last_login = datetime.utcnow()
            db.commit()

    @staticmethod
    def save_reset_token(db: Session, user_id: int, token: str):
        """Save password reset token"""
        # Implementation depends on your PasswordReset model
        pass

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        """Reset user password"""
        # Implementation depends on your PasswordReset model
        return True

    @staticmethod
    def verify_email(db: Session, token: str) -> bool:
        """Verify user email"""
        user = db.query(User).filter(User.verification_token == token).first()
        if user:
            user.email_verified = True
            user.verification_token = None
            db.commit()
            return True
        return False

    @staticmethod
    def update_user_profile(db: Session, user_id: int, update_data: dict) -> User:
        """Update user profile"""
        user = db.query(User).filter(User.id == user_id).first()
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user_id: int, new_password: str):
        """Change user password"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = SecurityUtils.get_password_hash(new_password)
            db.commit()
