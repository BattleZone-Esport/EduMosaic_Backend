"""
AI integration endpoints
Handles AI-powered features like quiz generation and recommendations
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import User
from app.schemas.ai import (
    ContentSummaryRequest,
    ContentSummaryResponse,
    QuizGenerationRequest,
    QuizGenerationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.ai import AIService

router = APIRouter()


@router.post("/generate/quiz", response_model=QuizGenerationResponse)
async def generate_quiz(
    request: QuizGenerationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate a quiz using AI

    - **topic**: Topic for the quiz
    - **difficulty**: Difficulty level
    - **num_questions**: Number of questions to generate
    - **question_types**: Types of questions to include
    """
    if not settings.FEATURE_AI_QUIZ_GENERATION:
        raise HTTPException(status_code=503, detail="AI quiz generation is currently disabled")

    try:
        quiz = await AIService.generate_quiz(
            topic=request.topic,
            difficulty=request.difficulty,
            num_questions=request.num_questions,
            question_types=request.question_types,
            user_id=current_user.id,
        )
        return quiz
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")


@router.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized recommendations

    - **recommendation_type**: Type of recommendation (quiz, topic, study_plan)
    - **context**: Additional context for recommendations
    """
    if not settings.FEATURE_RECOMMENDATION_ENGINE:
        raise HTTPException(status_code=503, detail="Recommendation engine is currently disabled")

    try:
        recommendations = await AIService.get_recommendations(
            user_id=current_user.id,
            recommendation_type=request.recommendation_type,
            context=request.context,
            db=db,
        )
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")


@router.post("/summarize", response_model=ContentSummaryResponse)
async def summarize_content(
    request: ContentSummaryRequest, current_user: User = Depends(get_current_active_user)
):
    """
    Summarize educational content using AI

    - **content**: Content to summarize
    - **summary_length**: Desired summary length (short, medium, long)
    - **format**: Output format (bullet_points, paragraph, key_concepts)
    """
    if not settings.AI_ENABLED:
        raise HTTPException(status_code=503, detail="AI services are currently disabled")

    try:
        summary = await AIService.summarize_content(
            content=request.content, summary_length=request.summary_length, format=request.format
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content summarization failed: {str(e)}")


@router.post("/analyze/performance")
async def analyze_performance(
    time_period: str = "last_30_days",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Analyze user's performance using AI

    Returns insights and recommendations based on quiz performance
    """
    if not settings.AI_ENABLED:
        raise HTTPException(status_code=503, detail="AI services are currently disabled")

    try:
        analysis = await AIService.analyze_user_performance(
            user_id=current_user.id, time_period=time_period, db=db
        )
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance analysis failed: {str(e)}")


@router.post("/generate/study-plan")
async def generate_study_plan(
    goal: str,
    timeline: str,
    current_level: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate personalized study plan using AI

    - **goal**: Learning goal
    - **timeline**: Target timeline
    - **current_level**: Current knowledge level
    """
    if not settings.AI_ENABLED:
        raise HTTPException(status_code=503, detail="AI services are currently disabled")

    try:
        study_plan = await AIService.generate_study_plan(
            user_id=current_user.id,
            goal=goal,
            timeline=timeline,
            current_level=current_level,
            db=db,
        )
        return study_plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Study plan generation failed: {str(e)}")


@router.get("/status")
async def get_ai_service_status():
    """Get AI service status and available features"""
    return {
        "enabled": settings.AI_ENABLED,
        "features": {
            "quiz_generation": settings.FEATURE_AI_QUIZ_GENERATION,
            "recommendations": settings.FEATURE_RECOMMENDATION_ENGINE,
            "content_summary": settings.AI_ENABLED,
            "performance_analysis": settings.AI_ENABLED,
            "study_plan_generation": settings.AI_ENABLED,
        },
        "model": settings.AI_MODEL if settings.AI_ENABLED else None,
        "service_url": bool(settings.AI_SERVICE_URL) if settings.AI_ENABLED else False,
    }
