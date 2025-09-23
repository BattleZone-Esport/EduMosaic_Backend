"""
Custom exceptions and error handlers for EduMosaic Backend
Provides consistent error responses and logging
"""

import logging
from typing import Any, Dict, Optional

import sentry_sdk
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class EduMosaicException(Exception):
    """Base exception for EduMosaic application"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class DatabaseException(EduMosaicException):
    """Database operation exception"""

    def __init__(
        self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=details,
        )


class AuthenticationException(EduMosaicException):
    """Authentication exception"""

    def __init__(
        self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )


class AuthorizationException(EduMosaicException):
    """Authorization exception"""

    def __init__(
        self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHORIZATION_ERROR",
            details=details,
        )


class ValidationException(EduMosaicException):
    """Validation exception"""

    def __init__(
        self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class NotFoundException(EduMosaicException):
    """Resource not found exception"""

    def __init__(self, resource: str = "Resource", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details=details,
        )


class DuplicateException(EduMosaicException):
    """Duplicate resource exception"""

    def __init__(self, resource: str = "Resource", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{resource} already exists",
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_ERROR",
            details=details,
        )


class RateLimitException(EduMosaicException):
    """Rate limit exceeded exception"""

    def __init__(
        self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_ERROR",
            details=details,
        )


class ExternalServiceException(EduMosaicException):
    """External service exception"""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{service}: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details,
        )


class FileUploadException(EduMosaicException):
    """File upload exception"""

    def __init__(
        self, message: str = "File upload failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="FILE_UPLOAD_ERROR",
            details=details,
        )


class QuizException(EduMosaicException):
    """Quiz-related exception"""

    def __init__(
        self, message: str = "Quiz operation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="QUIZ_ERROR",
            details=details,
        )


class AIServiceException(EduMosaicException):
    """AI service exception"""

    def __init__(self, message: str = "AI service error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="AI_SERVICE_ERROR",
            details=details,
        )


def create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    Create standardized error response

    Args:
        request: FastAPI request object
        status_code: HTTP status code
        error_code: Application error code
        message: Error message
        details: Additional error details

    Returns:
        JSON response with error information
    """
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
            "path": str(request.url),
            "method": request.method,
        }
    }

    # Add request ID if available
    if hasattr(request.state, "request_id"):
        error_response["error"]["request_id"] = request.state.request_id

    return JSONResponse(status_code=status_code, content=error_response)


async def edumosaic_exception_handler(request: Request, exc: EduMosaicException) -> JSONResponse:
    """
    Handle EduMosaic custom exceptions

    Args:
        request: FastAPI request object
        exc: EduMosaic exception

    Returns:
        JSON error response
    """
    logger.error(
        f"EduMosaic exception: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": str(request.url),
        },
    )

    # Send to Sentry if configured
    if settings.SENTRY_DSN and exc.status_code >= 500:
        sentry_sdk.capture_exception(exc)

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions

    Args:
        request: FastAPI request object
        exc: HTTP exception

    Returns:
        JSON error response
    """
    logger.warning(
        f"HTTP exception: {exc.detail}",
        extra={"status_code": exc.status_code, "path": str(request.url)},
    )

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        message=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors

    Args:
        request: FastAPI request object
        exc: Validation error

    Returns:
        JSON error response with validation details
    """
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning("Validation error", extra={"errors": errors, "path": str(request.url)})

    return create_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": errors},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions

    Args:
        request: FastAPI request object
        exc: Any exception

    Returns:
        JSON error response
    """
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={"exception_type": type(exc).__name__, "path": str(request.url)},
        exc_info=True,
    )

    # Send to Sentry if configured
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(exc)

    # Don't expose internal errors in production
    if settings.is_production():
        message = "An unexpected error occurred"
    else:
        message = str(exc)

    return create_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        message=message,
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(EduMosaicException, edumosaic_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Catch-all handler for unexpected exceptions
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
