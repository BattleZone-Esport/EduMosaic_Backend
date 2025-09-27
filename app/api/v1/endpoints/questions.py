"""
Question management endpoints
Handles question creation, retrieval, and management
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user, require_role
from app.models import User
from app.schemas.questions import QuestionCreate, QuestionResponse
from app.services.questions import QuestionService

router = APIRouter()


@router.get("/", response_model=List[QuestionResponse])
async def get_questions(
    quiz_id: Optional[int] = None,
    category_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get list of questions with filters"""
    return QuestionService.get_questions(db, quiz_id, category_id, skip, limit)


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: int, db: Session = Depends(get_db)):
    """Get question by ID"""
    question = QuestionService.get_question(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.post("/", response_model=QuestionResponse)
async def create_question(
    question_data: QuestionCreate,
    current_user: User = Depends(require_role(["ADMIN", "CONTENT_CREATOR"])),
    db: Session = Depends(get_db),
):
    """Create a new question"""
    return QuestionService.create_question(db, question_data, current_user)


@router.put("/{question_id}")
async def update_question(
    question_id: int,
    question_data: dict,
    current_user: User = Depends(require_role(["ADMIN", "CONTENT_CREATOR"])),
    db: Session = Depends(get_db),
):
    """Update question"""
    return QuestionService.update_question(db, question_id, question_data, current_user)


@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """Delete question"""
    QuestionService.delete_question(db, question_id)
    return {"message": "Question deleted successfully"}
