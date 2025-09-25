"""
Rate limiting middleware for EduMosaic Backend
Protects against abuse and ensures fair resource usage
"""

import logging
import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import cache_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom rate limiting middleware with Redis backend
    Falls back gracefully if Redis is unavailable
    """

    def __init__(self, app, default_limits: str = None):
        super().__init__(app)
        self.default_limits = default_limits or settings.RATE_LIMIT_DEFAULT
        self.enabled = settings.RATE_LIMIT_ENABLED

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler or rate limit error
        """
        if not self.enabled:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        if await self._is_rate_limited(client_id, request.url.path):
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        await self._add_rate_limit_headers(response, client_id)

        return response

    def _get_client_id(self, request: Request) -> str:
        """
        Get unique client identifier from request

        Args:
            request: Incoming request

        Returns:
            Client identifier string
        """
        # Try to get authenticated user ID first
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        return f"ip:{get_remote_address(request)}"

    async def _is_rate_limited(self, client_id: str, path: str) -> bool:
        """
        Check if client has exceeded rate limit

        Args:
            client_id: Client identifier
            path: Request path

        Returns:
            True if rate limited, False otherwise
        """
        if not cache_manager.connected:
            # If Redis is down, allow requests but log warning
            logger.warning("Redis unavailable, rate limiting disabled")
            return False

        # Build rate limit key
        window = int(time.time() // 60)  # 1-minute window
        key = f"rate_limit:{client_id}:{window}"

        # Get current count
        count = await cache_manager.increment(key)

        if count == 1:
            # Set expiration on first request in window
            await cache_manager.redis_client.expire(key, 60)

        # Parse limit from settings
        limit = self._get_limit_for_path(path)

        return count > limit

    def _get_limit_for_path(self, path: str) -> int:
        """
        Get rate limit for specific path

        Args:
            path: Request path

        Returns:
            Rate limit as integer
        """
        # Auth endpoints have stricter limits
        if "/auth/" in path:
            return self._parse_limit(settings.RATE_LIMIT_AUTH)

        # Default limit
        return self._parse_limit(self.default_limits)

    def _parse_limit(self, limit_str: str) -> int:
        """
        Parse rate limit string to integer

        Args:
            limit_str: Rate limit string (e.g., "200 per minute")

        Returns:
            Limit as integer
        """
        try:
            parts = limit_str.split()
            return int(parts[0])
        except (ValueError, IndexError):
            return 200  # Default fallback

    async def _add_rate_limit_headers(self, response: Response, client_id: str):
        """
        Add rate limit headers to response

        Args:
            response: Response object
            client_id: Client identifier
        """
        if not cache_manager.connected:
            return

        try:
            window = int(time.time() // 60)
            key = f"rate_limit:{client_id}:{window}"

            count = await cache_manager.get(key)
            if count:
                limit = self._parse_limit(self.default_limits)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(max(0, limit - int(count)))
                response.headers["X-RateLimit-Reset"] = str((window + 1) * 60)
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")


def create_limiter() -> Limiter:
    """
    Create Limiter instance for use with decorators

    Returns:
        Configured Limiter instance
    """
    storage_uri = settings.get_redis_url() if settings.REDIS_ENABLED else None

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
        storage_uri=storage_uri,
        enabled=settings.RATE_LIMIT_ENABLED,
    )

    return limiter


# Global limiter instance
limiter = create_limiter()


def rate_limit(limits: str):
    """
    Decorator for applying rate limits to specific endpoints

    Args:
        limits: Rate limit string (e.g., "5 per minute")

    Example:
        @router.get("/api/endpoint")
        @rate_limit("10 per minute")
        async def endpoint():
            return {"message": "Limited endpoint"}
    """

    def decorator(func):
        return limiter.limit(limits)(func)

    return decorator
