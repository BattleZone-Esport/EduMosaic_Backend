"""
Rate limiting middleware for EduMosaic
"""

from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings

def add_rate_limiting(app: FastAPI):
    """Add rate limiting to application"""
    
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}seconds"]
    )
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Rate limiting middleware"""
        try:
            # Apply rate limiting
            with limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}seconds"):
                response = await call_next(request)
                return response
        except RateLimitExceeded:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
