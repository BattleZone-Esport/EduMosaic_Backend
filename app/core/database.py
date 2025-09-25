"""
Database configuration and session management
Handles connection pooling, retry logic, and monitoring
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator, Optional

import sentry_sdk
from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.exc import DisconnectionError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Base class for models
Base = declarative_base()

# Create engine with optimized settings
engine = create_engine(
    settings.get_db_url(),
    poolclass=pool.QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    echo=settings.DEBUG,
    connect_args={
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
        "options": "-c statement_timeout=60000",  # 60 seconds
    },
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Initialize database, create tables if they don't exist"""
    try:
        # Import all models here to ensure they're registered
        from app.models import models  # noqa

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if settings.SENTRY_DSN:
            sentry_sdk.capture_exception(e)
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    Ensures proper cleanup after request
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error occurred: {e}")
        db.rollback()
        if settings.SENTRY_DSN:
            sentry_sdk.capture_exception(e)
        raise
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database session
    Use this for background tasks or non-request contexts
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        if settings.SENTRY_DSN:
            sentry_sdk.capture_exception(e)
        raise
    finally:
        session.close()


class DatabaseHealthCheck:
    """Database health check utility"""

    @staticmethod
    def check_connection() -> dict:
        """Check database connection health"""
        start_time = time.time()
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    return {
                        "status": "healthy",
                        "response_time": time.time() - start_time,
                        "pool_size": engine.pool.size(),
                        "checked_in_connections": engine.pool.checkedin(),
                        "overflow": engine.pool.overflow(),
                        "total": engine.pool.checkedout(),
                    }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time": time.time() - start_time,
            }

    @staticmethod
    def get_table_stats() -> dict:
        """Get statistics about database tables"""
        try:
            with engine.connect() as conn:
                # Get table sizes
                result = conn.execute(
                    text(
                        """
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                        n_live_tup AS row_count
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """
                    )
                )

                tables = []
                for row in result:
                    tables.append(
                        {"schema": row[0], "table": row[1], "size": row[2], "rows": row[3]}
                    )

                return {"tables": tables}
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            return {"error": str(e)}


# Event listeners for connection pool monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new database connections"""
    connection_record.info["pid"] = dbapi_conn.get_backend_pid()
    logger.debug(f"New database connection established: PID {connection_record.info['pid']}")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkouts from pool"""
    pid = connection_record.info.get("pid", "unknown")
    logger.debug(f"Connection checked out from pool: PID {pid}")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log connection returns to pool"""
    pid = connection_record.info.get("pid", "unknown")
    logger.debug(f"Connection returned to pool: PID {pid}")


# Retry decorator for database operations
def with_db_retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Decorator to retry database operations on failure

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_attempts}): {e}"
                        )
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(
                            f"Database operation failed after {max_attempts} attempts: {e}"
                        )

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


# Database utilities
class DatabaseUtils:
    """Utility functions for database operations"""

    @staticmethod
    def vacuum_analyze(table_name: Optional[str] = None):
        """Run VACUUM ANALYZE on table or entire database"""
        try:
            with engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                if table_name:
                    conn.execute(text(f"VACUUM ANALYZE {table_name}"))
                    logger.info(f"VACUUM ANALYZE completed for table: {table_name}")
                else:
                    conn.execute(text("VACUUM ANALYZE"))
                    logger.info("VACUUM ANALYZE completed for entire database")
        except Exception as e:
            logger.error(f"VACUUM ANALYZE failed: {e}")
            raise

    @staticmethod
    def reset_sequence(table_name: str, column_name: str = "id"):
        """Reset auto-increment sequence for a table"""
        try:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', '{column_name}'),
                        COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1)
                    )
                """
                    )
                )
                logger.info(f"Reset sequence for {table_name}.{column_name}")
        except Exception as e:
            logger.error(f"Failed to reset sequence: {e}")
            raise
