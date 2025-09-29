"""
Quiz schemas for EduMosaic
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.quiz import DifficultyLevel, QuizCategory, Language

class QuestionBase(BaseModel):
    """Base question schema"""
    question_text: str
    question_type: str = "multiple_choice"
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_answer: str
    explanation: Optional[str] = None
    points: int = 10
    time_limit: Optional[int] = None
    hint: Optional[str] = None

class QuestionCreate(QuestionBase):
    """Question creation schema"""
    pass

class QuestionResponse(QuestionBase):
    """Question response schema"""
    id: int
    quiz_id: int
    image_url: Optional[str]
    order_number: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class QuizBase(BaseModel):
    """Base quiz schema"""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    category: QuizCategory
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    language: Language = Language.ENGLISH
    time_limit: Optional[int] = None
    passing_score: float = 60.0

class QuizCreate(QuizBase):
    """Quiz creation schema"""
    questions: List[QuestionCreate] = []
    tags: List[str] = []

class QuizUpdate(BaseModel):
    """Quiz update schema"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[QuizCategory] = None
    difficulty: Optional[DifficultyLevel] = None
    is_published: Optional[bool] = None

class QuizResponse(QuizBase):
    """Quiz response schema"""
    id: int
    created_by: int
    is_active: bool
    is_published: bool
    total_questions: int
    thumbnail_url: Optional[str]
    tags: List[str]
    times_taken: int
    average_score: float
    rating: float
    created_at: datetime
    questions: List[QuestionResponse] = []
    
    class Config:
        from_attributes = True

class QuizAttemptCreate(BaseModel):
    """Quiz attempt creation schema"""
    quiz_id: int
    answers: dict

class QuizAttemptResponse(BaseModel):
    """Quiz attempt response schema"""
    id: int
    user_id: int
    quiz_id: int
    score: float
    total_questions: int
    correct_answers: int
    time_taken: int
    started_at: datetime
    completed_at: datetime
    
    class Config:
        from_attributes = True
