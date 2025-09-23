"""
Leaderboard endpoints
Handles global and quiz-specific leaderboards
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache import cached
from app.core.database import get_db
from app.schemas.leaderboard import LeaderboardEntry
from app.services.leaderboard import LeaderboardService

router = APIRouter()


@router.get("/global", response_model=List[LeaderboardEntry])
@cached(expire=300, key_prefix="leaderboard:global")
async def get_global_leaderboard(
    period: str = Query("all", regex="^(daily|weekly|monthly|all)$"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get global leaderboard"""
    return LeaderboardService.get_global_leaderboard(db, period, limit)


@router.get("/category/{category_id}", response_model=List[LeaderboardEntry])
@cached(expire=300, key_prefix="leaderboard:category")
async def get_category_leaderboard(
    category_id: int,
    period: str = Query("all", regex="^(daily|weekly|monthly|all)$"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get category-specific leaderboard"""
    return LeaderboardService.get_category_leaderboard(db, category_id, period, limit)


@router.get("/user/{user_id}/rank")
async def get_user_rank(
    user_id: int, category_id: Optional[int] = None, db: Session = Depends(get_db)
):
    """Get user's rank in leaderboard"""
    return LeaderboardService.get_user_rank(db, user_id, category_id)
