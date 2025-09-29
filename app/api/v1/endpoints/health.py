"""
Health check endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.redis import cache
import psutil

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "EduMosaic Backend",
        "version": "2.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check"""
    health_status = {
        "status": "healthy",
        "service": "EduMosaic Backend",
        "version": "2.0.0",
        "checks": {}
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis
    health_status["checks"]["redis"] = "healthy" if cache.is_connected else "disconnected"
    
    # Check system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    health_status["checks"]["resources"] = {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_mb": memory.available / (1024 * 1024)
    }
    
    return health_status
