"""
User management endpoints
Handles user profiles, preferences, and user-related operations
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import User
from app.schemas.users import UserFilter, UserUpdate
from app.services.users import UserService

router = APIRouter()


@router.get("/", response_model=List[dict])
async def get_users(
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
):
    """Get list of users with pagination"""
    return UserService.get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID"""
    return UserService.get_user(db, user_id)


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update user information"""
    return UserService.update_user(db, user_id, user_data, current_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete user account"""
    UserService.delete_user(db, user_id, current_user)
    return None
