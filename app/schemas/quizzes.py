"""Quiz schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: int
    difficulty: str
    time_limit: Optional[int] = None
    passing_score: int = 60


class QuizResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category_id: int
    difficulty: str
    time_limit: Optional[int]
    passing_score: int
    created_at: datetime

    class Config:
        from_attributes = True


class QuizAttempt(BaseModel):
    answers: List[dict]
    time_taken: int
