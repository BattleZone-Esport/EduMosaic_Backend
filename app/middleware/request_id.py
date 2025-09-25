"""
Request ID middleware for EduMosaic Backend
Adds unique request ID for tracing and debugging
"""

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request ID to each request
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add request ID to request and response

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with request ID header
        """
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state
        request.state.request_id = request_id

        # Add to logging context
        logger.debug(f"Processing request {request_id}: {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
