"""Question schemas"""

from typing import List, Optional

from pydantic import BaseModel


class QuestionCreate(BaseModel):
    quiz_id: int
    question_text: str
    question_type: str
    options: List[dict]
    correct_answer: str
    explanation: Optional[str] = None
    points: int = 1


class QuestionResponse(BaseModel):
    id: int
    question_text: str
    question_type: str
    options: List[dict]
    points: int

    class Config:
        from_attributes = True
