"""
System endpoints
Handles system information and monitoring
"""

import os
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cache import cache_manager
from app.core.config import settings
from app.core.database import DatabaseHealthCheck, get_db

router = APIRouter()


@router.get("/info")
async def get_system_info():
    """Get system information"""
    return {
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "python_version": "3.12",
        "api_versions": {"v1": settings.API_V1_STR, "v2": settings.API_V2_STR},
    }


@router.get("/status")
async def get_system_status():
    """Get system status and metrics"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational",
        "metrics": {
            "cpu": {"usage_percent": cpu_percent, "cores": psutil.cpu_count()},
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            },
        },
        "services": {
            "database": DatabaseHealthCheck.check_connection()["status"],
            "redis": "connected" if cache_manager.connected else "disconnected",
        },
    }


@router.get("/config")
async def get_public_config():
    """Get public configuration settings"""
    return {
        "features": {
            "social_login": settings.FEATURE_SOCIAL_LOGIN,
            "payment": settings.FEATURE_PAYMENT,
            "chat": settings.FEATURE_CHAT,
            "video_quiz": settings.FEATURE_VIDEO_QUIZ,
            "ai_quiz_generation": settings.FEATURE_AI_QUIZ_GENERATION,
            "recommendation_engine": settings.FEATURE_RECOMMENDATION_ENGINE,
        },
        "limits": {
            "max_upload_size": settings.MAX_UPLOAD_SIZE,
            "default_page_size": settings.DEFAULT_PAGE_SIZE,
            "max_page_size": settings.MAX_PAGE_SIZE,
        },
        "gamification": {
            "xp_per_correct_answer": settings.XP_PER_CORRECT_ANSWER,
            "xp_per_quiz_completion": settings.XP_PER_QUIZ_COMPLETION,
            "xp_per_level": settings.XP_PER_LEVEL,
        },
    }
