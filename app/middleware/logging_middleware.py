"""
Logging middleware for EduMosaic Backend
Logs all requests and responses with timing information
"""

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger("edumosaic.request")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request and response details

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Skip logging for health check endpoints
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Get request details
        request_id = getattr(request.state, "request_id", "unknown")

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "client": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 3),
                    "success": 200 <= response.status_code < 400,
                },
            )

            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time

            # Log error
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": round(process_time, 3),
                    "error": str(e),
                    "success": False,
                },
                exc_info=True,
            )

            raise
