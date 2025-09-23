"""
Achievement and badge endpoints
Handles user achievements, badges, and rewards
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import User
from app.schemas.achievements import AchievementResponse, BadgeResponse
from app.services.achievements import AchievementService

router = APIRouter()


@router.get("/", response_model=List[AchievementResponse])
async def get_achievements(db: Session = Depends(get_db)):
    """Get all available achievements"""
    return AchievementService.get_all_achievements(db)


@router.get("/user/{user_id}", response_model=List[AchievementResponse])
async def get_user_achievements(user_id: int, db: Session = Depends(get_db)):
    """Get user's achievements"""
    return AchievementService.get_user_achievements(db, user_id)


@router.get("/badges", response_model=List[BadgeResponse])
async def get_badges(db: Session = Depends(get_db)):
    """Get all available badges"""
    return AchievementService.get_all_badges(db)


@router.get("/user/{user_id}/badges", response_model=List[BadgeResponse])
async def get_user_badges(user_id: int, db: Session = Depends(get_db)):
    """Get user's badges"""
    return AchievementService.get_user_badges(db, user_id)


@router.post("/check")
async def check_achievements(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Check and award pending achievements for current user"""
    new_achievements = AchievementService.check_and_award_achievements(db, current_user)
    return {"new_achievements": new_achievements}
