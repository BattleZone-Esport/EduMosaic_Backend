"""
CORS configuration for EduMosaic Backend
DO NOT MODIFY without explicit permission
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware
    IMPORTANT: Do not change existing CORS settings

    Args:
        app: FastAPI application instance
    """

    # Get allowed origins
    if settings.CORS_ALLOW_ALL_ORIGINS:
        allow_origins = ["*"]
    else:
        allow_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]

    # Add CORS middleware with existing configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
