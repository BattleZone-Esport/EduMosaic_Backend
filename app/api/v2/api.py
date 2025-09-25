"""
API v2 main router
Placeholder for future API v2 endpoints
"""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/")
async def v2_root():
    """API v2 root endpoint"""
    return {
        "message": "API v2 - Coming Soon",
        "status": "Under Development",
        "info": "This version will include enhanced features and improved performance",
    }
