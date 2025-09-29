"""
Quiz endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.quiz import Quiz, Question, QuizAttempt
from app.schemas.quiz import (
    QuizCreate, QuizResponse, QuizUpdate,
    QuizAttemptCreate, QuizAttemptResponse
)
from app.services.auth import auth_service
from app.api.v1.endpoints.auth import oauth2_scheme
from datetime import datetime

router = APIRouter()

@router.get("/", response_model=List[QuizResponse])
async def get_quizzes(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all quizzes with pagination and filters"""
    query = db.query(Quiz).filter(Quiz.is_published == True, Quiz.is_active == True)
    
    if category:
        query = query.filter(Quiz.category == category)
    if difficulty:
        query = query.filter(Quiz.difficulty == difficulty)
    
    quizzes = query.offset(skip).limit(limit).all()
    return quizzes

@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Get specific quiz by ID"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.is_active == True).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    return quiz

@router.post("/", response_model=QuizResponse)
async def create_quiz(
    quiz_create: QuizCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Create new quiz (teachers and admins only)"""
    user = auth_service.get_current_user(db, token)
    if not user or user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create quizzes"
        )
    
    # Create quiz
    quiz = Quiz(
        **quiz_create.dict(exclude={"questions"}),
        created_by=user.id
    )
    db.add(quiz)
    db.flush()
    
    # Add questions
    for q_data in quiz_create.questions:
        question = Question(**q_data.dict(), quiz_id=quiz.id)
        db.add(question)
    
    quiz.total_questions = len(quiz_create.questions)
    db.commit()
    db.refresh(quiz)
    
    return quiz

@router.put("/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    quiz_id: int,
    quiz_update: QuizUpdate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Update quiz"""
    user = auth_service.get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    if quiz.created_by != user.id and user.role not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this quiz"
        )
    
    for field, value in quiz_update.dict(exclude_unset=True).items():
        setattr(quiz, field, value)
    
    db.commit()
    db.refresh(quiz)
    return quiz

@router.post("/attempt", response_model=QuizAttemptResponse)
async def submit_quiz_attempt(
    attempt: QuizAttemptCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Submit quiz attempt"""
    user = auth_service.get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Get quiz
    quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    # Calculate score
    questions = db.query(Question).filter(Question.quiz_id == quiz.id).all()
    correct_answers = 0
    total_points = 0
    earned_points = 0
    
    for question in questions:
        total_points += question.points
        user_answer = attempt.answers.get(str(question.id))
        if user_answer == question.correct_answer:
            correct_answers += 1
            earned_points += question.points
    
    score = (earned_points / total_points * 100) if total_points > 0 else 0
    
    # Save attempt
    quiz_attempt = QuizAttempt(
        user_id=user.id,
        quiz_id=quiz.id,
        score=score,
        total_questions=len(questions),
        correct_answers=correct_answers,
        time_taken=0,  # Should be calculated from frontend
        answers=attempt.answers,
        started_at=datetime.utcnow()
    )
    
    db.add(quiz_attempt)
    
    # Update user stats
    user.quizzes_taken += 1
    user.total_score += earned_points
    
    # Update quiz stats
    quiz.times_taken += 1
    
    db.commit()
    db.refresh(quiz_attempt)
    
    return quiz_attempt
