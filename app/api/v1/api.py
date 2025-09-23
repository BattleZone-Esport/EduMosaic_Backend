"""
API v1 main router
Combines all v1 endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    achievements,
    admin,
    ai,
    auth,
    leaderboard,
    notifications,
    questions,
    quizzes,
    system,
    users,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["Quizzes"])
api_router.include_router(questions.router, prefix="/questions", tags=["Questions"])
api_router.include_router(leaderboard.router, prefix="/leaderboard", tags=["Leaderboard"])
api_router.include_router(achievements.router, prefix="/achievements", tags=["Achievements"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
