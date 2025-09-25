"""
Logging configuration for EduMosaic Backend
Sets up structured logging with rotation and multiple outputs
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "environment": settings.ENVIRONMENT,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data)


def setup_logging() -> None:
    """
    Configure application logging
    Sets up console and file handlers with appropriate formatters
    """

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Clear existing handlers
    root_logger.handlers = []

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    if settings.is_production():
        # Use JSON format in production
        console_formatter = JSONFormatter()
    else:
        # Use readable format in development
        console_formatter = logging.Formatter(fmt=settings.LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.LOG_FILE,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    # Always use JSON format for file logs
    file_formatter = JSONFormatter()
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Error File Handler
    error_file_handler = logging.handlers.RotatingFileHandler(
        filename="logs/error.log",
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_file_handler)

    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if settings.is_production() else logging.INFO
    )
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    root_logger.info(
        "Logging configured",
        extra={
            "environment": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL,
            "log_file": settings.LOG_FILE,
        },
    )


class LoggerFactory:
    """Factory for creating loggers with consistent configuration"""

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger instance with the given name

        Args:
            name: Logger name (usually __name__)

        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)

    @staticmethod
    def get_request_logger() -> logging.Logger:
        """Get logger for request/response logging"""
        return logging.getLogger("edumosaic.request")

    @staticmethod
    def get_security_logger() -> logging.Logger:
        """Get logger for security events"""
        logger = logging.getLogger("edumosaic.security")

        # Add special handler for security events
        security_handler = logging.handlers.RotatingFileHandler(
            filename="logs/security.log",
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        security_handler.setLevel(logging.INFO)
        security_handler.setFormatter(JSONFormatter())

        if not logger.handlers:
            logger.addHandler(security_handler)

        return logger

    @staticmethod
    def get_audit_logger() -> logging.Logger:
        """Get logger for audit events"""
        logger = logging.getLogger("edumosaic.audit")

        # Add special handler for audit events
        audit_handler = logging.handlers.RotatingFileHandler(
            filename="logs/audit.log",
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(JSONFormatter())

        if not logger.handlers:
            logger.addHandler(audit_handler)

        return logger


class LogContext:
    """Context manager for adding context to log messages"""

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_context = {}

    def __enter__(self):
        """Add context to logger"""
        for key, value in self.context.items():
            if hasattr(self.logger, key):
                self.old_context[key] = getattr(self.logger, key)
            setattr(self.logger, key, value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove context from logger"""
        for key in self.context:
            if key in self.old_context:
                setattr(self.logger, key, self.old_context[key])
            else:
                delattr(self.logger, key)


def log_execution_time(logger: logging.Logger = None):
    """
    Decorator to log function execution time

    Args:
        logger: Logger instance to use
    """
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                log = logger or logging.getLogger(func.__module__)
                log.info(
                    f"Function {func.__name__} executed successfully",
                    extra={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "success": True,
                    },
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time

                log = logger or logging.getLogger(func.__module__)
                log.error(
                    f"Function {func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "success": False,
                        "error": str(e),
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                log = logger or logging.getLogger(func.__module__)
                log.info(
                    f"Function {func.__name__} executed successfully",
                    extra={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "success": True,
                    },
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time

                log = logger or logging.getLogger(func.__module__)
                log.error(
                    f"Function {func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "execution_time": execution_time,
                        "success": False,
                        "error": str(e),
                    },
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
