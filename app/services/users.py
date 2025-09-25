"""User service"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import User


class UserService:
    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 20) -> List[User]:
        """Get list of users"""
        return db.query(User).offset(skip).limit(limit).all()

    @staticmethod
    def get_user(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user(db: Session, user_id: int, user_data, current_user) -> User:
        """Update user information"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Check permissions
        if current_user.id != user_id and current_user.role not in ["ADMIN", "SUPER_ADMIN"]:
            raise PermissionError("Insufficient permissions")

        # Update fields
        for key, value in user_data.dict(exclude_unset=True).items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int, current_user):
        """Delete user account"""
        if current_user.id != user_id and current_user.role not in ["ADMIN", "SUPER_ADMIN"]:
            raise PermissionError("Insufficient permissions")

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
