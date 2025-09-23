"""
Quiz management endpoints
Handles quiz creation, retrieval, and management
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import User
from app.schemas.quizzes import QuizAttempt, QuizCreate, QuizResponse
from app.services.quizzes import QuizService

router = APIRouter()


@router.get("/", response_model=List[QuizResponse])
async def get_quizzes(
    category_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get list of quizzes with filters"""
    return QuizService.get_quizzes(db, category_id, difficulty, skip, limit)


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Get quiz by ID"""
    quiz = QuizService.get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.post("/", response_model=QuizResponse)
async def create_quiz(
    quiz_data: QuizCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new quiz"""
    return QuizService.create_quiz(db, quiz_data, current_user)


@router.post("/{quiz_id}/attempt")
async def submit_quiz_attempt(
    quiz_id: int,
    attempt: QuizAttempt,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Submit quiz attempt and get results"""
    return QuizService.process_quiz_attempt(db, quiz_id, attempt, current_user)


@router.get("/{quiz_id}/leaderboard")
async def get_quiz_leaderboard(
    quiz_id: int, limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)
):
    """Get quiz leaderboard"""
    return QuizService.get_quiz_leaderboard(db, quiz_id, limit)
