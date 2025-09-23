"""AI schemas"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuizGenerationRequest(BaseModel):
    topic: str
    difficulty: str = "medium"
    num_questions: int = Field(10, ge=1, le=50)
    question_types: Optional[List[str]] = None


class QuizGenerationResponse(BaseModel):
    quiz_id: Optional[int]
    title: str
    questions: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class RecommendationRequest(BaseModel):
    recommendation_type: str
    context: Optional[Dict[str, Any]] = None


class RecommendationResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    confidence_scores: List[float]


class ContentSummaryRequest(BaseModel):
    content: str
    summary_length: str = "medium"
    format: str = "paragraph"


class ContentSummaryResponse(BaseModel):
    summary: str
    key_points: List[str]
    word_count: int
