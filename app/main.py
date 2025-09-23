"""
Main application entry point for EduMosaic Backend
Configures FastAPI app with all middleware, routers, and services
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# Import API routers
from app.api.v1.api import api_router as v1_router
from app.api.v2.api import api_router as v2_router
from app.core.cache import cache_manager
from app.core.config import settings
from app.core.database import DatabaseHealthCheck, engine, init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

# Import middleware
from app.middleware import (
    LoggingMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    setup_cors,
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Store startup time for uptime calculation
startup_time = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting EduMosaic Backend...")

    # Initialize Sentry if configured
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,
        )
        logger.info("Sentry initialized")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if not settings.is_development():
            raise

    # Connect to Redis cache
    if settings.REDIS_ENABLED:
        connected = await cache_manager.connect()
        if connected:
            logger.info("Redis cache connected")
        else:
            logger.warning("Redis cache connection failed - running without cache")

    # Run Alembic migrations automatically
    if settings.is_production():
        try:
            import subprocess

            result = subprocess.run(
                ["alembic", "upgrade", "head"], capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info("Database migrations completed successfully")
            else:
                logger.error(f"Database migration failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")

    logger.info(f"EduMosaic Backend started successfully in {settings.ENVIRONMENT} mode")

    yield

    # Shutdown
    logger.info("Shutting down EduMosaic Backend...")

    # Disconnect from Redis
    if cache_manager.connected:
        await cache_manager.disconnect()
        logger.info("Redis cache disconnected")

    # Close database connections
    engine.dispose()
    logger.info("Database connections closed")

    logger.info("EduMosaic Backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if not settings.is_production() else None,
    docs_url="/docs" if not settings.is_production() else None,
    redoc_url="/redoc" if not settings.is_production() else None,
    lifespan=lifespan,
)

# Register exception handlers
register_exception_handlers(app)

# Add middleware in correct order (CORS should be first)
setup_cors(app)  # CORS middleware - DO NOT MODIFY

# Add custom middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Add Sentry middleware if configured
if settings.SENTRY_DSN:
    app.add_middleware(SentryAsgiMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount Prometheus metrics endpoint
if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# Include API routers
app.include_router(v1_router, prefix=settings.API_V1_STR)
app.include_router(v2_router, prefix=settings.API_V2_STR)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "api_v1": settings.API_V1_STR,
        "api_v2": settings.API_V2_STR,
        "documentation": "/docs" if not settings.is_production() else None,
        "health": "/health",
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring
    Returns system health status
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": (datetime.utcnow() - startup_time).total_seconds(),
    }

    # Check database health
    db_health = DatabaseHealthCheck.check_connection()
    health_status["database"] = db_health

    # Check Redis health
    if settings.REDIS_ENABLED:
        redis_health = {
            "status": "healthy" if cache_manager.connected else "unhealthy",
            "connected": cache_manager.connected,
        }
        health_status["redis"] = redis_health

    # Determine overall health
    if db_health["status"] == "unhealthy":
        health_status["status"] = "degraded"
        return JSONResponse(status_code=503, content=health_status)

    return health_status


# Ready check endpoint
@app.get("/ready", tags=["Health"])
async def ready_check():
    """
    Readiness check endpoint for Kubernetes/container orchestration
    Returns whether the service is ready to accept traffic
    """
    # Check if all critical services are ready
    db_health = DatabaseHealthCheck.check_connection()

    if db_health["status"] == "unhealthy":
        return JSONResponse(
            status_code=503, content={"ready": False, "reason": "Database not ready"}
        )

    return {"ready": True, "timestamp": datetime.utcnow().isoformat()}


# Version endpoint
@app.get("/version", tags=["System"])
async def version():
    """Get application version information"""
    return {
        "version": settings.VERSION,
        "api_v1": settings.API_V1_STR,
        "api_v2": settings.API_V2_STR,
        "python_version": "3.12",
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development(),
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
