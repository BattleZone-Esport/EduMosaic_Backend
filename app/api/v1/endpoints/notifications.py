"""
Notification endpoints
Handles user notifications and alerts
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import User
from app.schemas.notifications import NotificationResponse
from app.services.notifications import NotificationService

router = APIRouter()


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get user's notifications"""
    return NotificationService.get_user_notifications(db, current_user.id, unread_only, skip, limit)


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark notification as read"""
    NotificationService.mark_as_read(db, notification_id, current_user.id)
    return {"message": "Notification marked as read"}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Mark all notifications as read"""
    NotificationService.mark_all_as_read(db, current_user.id)
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a notification"""
    NotificationService.delete_notification(db, notification_id, current_user.id)
    return {"message": "Notification deleted"}
