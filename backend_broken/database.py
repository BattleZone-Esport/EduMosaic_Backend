from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import os
import time
import logging
from dotenv import load_dotenv
from contextlib import contextmanager
from prometheus_client import Counter, Gauge, Histogram
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

load_dotenv()

# Metrics for monitoring
DB_CONNECTION_ATTEMPTS = Counter('db_connection_attempts', 'Database connection attempts')
DB_CONNECTION_ERRORS = Counter('db_connection_errors', 'Database connection errors')
DB_CONNECTION_ACTIVE = Gauge('db_connection_active', 'Active database connections')
DB_QUERY_TIME = Histogram('db_query_time_seconds', 'Database query time in seconds', 
                          buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
DB_QUERY_COUNT = Counter('db_query_count', 'Total database queries', ['operation'])

# Railway PostgreSQL connection
DATABASE_URL = os.getenv("DATABASE_URL")

# Use psycopg3 dialect for psycopg package
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Connection pool configuration
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "3"))
CONNECT_RETRY_DELAY = int(os.getenv("DB_CONNECT_RETRY_DELAY", "2"))  # seconds

# Engine with pooling for production stability
def create_db_engine():
    """Create database engine with retry mechanism"""
    retries = 0
    while retries < CONNECT_RETRIES:
        try:
            DB_CONNECTION_ATTEMPTS.inc()
            engine = create_engine(
                DATABASE_URL,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=POOL_TIMEOUT,
                pool_recycle=POOL_RECYCLE,
                pool_pre_ping=POOL_PRE_PING,
                echo=os.getenv("DB_ECHO", "false").lower() == "true",
                connect_args={
                    "connect_timeout": 10,
                    "application_name": f"edumosaic-app-{os.getenv('RAILWAY_REPLICA_ID', 'primary')}"
                },
                # Use server-side cursors for large result sets
                server_side_cursors=False,
                # JSON support
                json_serializer=lambda obj: obj,
                json_deserializer=lambda obj: obj
            )
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Database connection established successfully")
            DB_CONNECTION_ACTIVE.set(1)
            return engine
            
        except OperationalError as e:
            retries += 1
            DB_CONNECTION_ERRORS.inc()
            logger.warning(f"Database connection failed (attempt {retries}/{CONNECT_RETRIES}): {e}")
            
            if retries >= CONNECT_RETRIES:
                logger.error("Max database connection retries reached. Application will exit.")
                raise
            
            time.sleep(CONNECT_RETRY_DELAY * retries)  # Exponential backoff
            
        except Exception as e:
            logger.error(f"Unexpected error during database connection: {e}")
            raise

# Create engine with retry mechanism
engine = create_db_engine()

# Session factory with scoped sessions for thread safety
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Better performance for read-heavy apps
))

Base = declarative_base()

# Database health check
def check_db_health():
    """Check if database is responsive"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS health_check"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Connection pool stats
def get_pool_stats():
    """Get connection pool statistics"""
    return {
        "checkedout": engine.pool.checkedout(),
        "checkedin": engine.pool.checkedin(),
        "overflow": engine.pool.overflow(),
        "size": engine.pool.size(),
        "max_overflow": engine.pool.max_overflow()
    }

# Database version info
def get_db_version():
    """Get database version information"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            return result.scalar()
    except Exception as e:
        logger.error(f"Failed to get database version: {e}")
        return "Unknown"

# Query performance monitoring
@contextmanager
def db_query_monitor(operation="query"):
    """Context manager to monitor query performance"""
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        DB_QUERY_TIME.observe(duration)
        DB_QUERY_COUNT.labels(operation=operation).inc()
        
        if duration > 1.0:  # Log slow queries
            logger.warning(f"Slow query detected: {operation} took {duration:.3f}s")
            
    except Exception as e:
        duration = time.time() - start_time
        DB_QUERY_TIME.observe(duration)
        DB_QUERY_COUNT.labels(operation=f"error_{operation}").inc()
        logger.error(f"Query error after {duration:.3f}s: {e}")
        raise

# Database session dependency with monitoring
def get_db():
    """
    Dependency function that yields a database session.
    Automatically handles cleanup and includes monitoring.
    """
    db = SessionLocal()
    try:
        with db_query_monitor("session_creation"):
            yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        with db_query_monitor("session_cleanup"):
            db.close()

# Context manager for explicit transaction handling
@contextmanager
def transaction():
    """
    Context manager for handling database transactions.
    Usage:
        with transaction() as db:
            # your database operations
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
    finally:
        db.close()

# Database maintenance tasks
def run_maintenance():
    """Run database maintenance tasks"""
    try:
        with engine.connect() as conn:
            # Update statistics for query optimization
            conn.execute(text("ANALYZE"))
            logger.info("Database maintenance completed")
    except Exception as e:
        logger.error(f"Database maintenance failed: {e}")

# Periodic health check and maintenance
def start_db_watcher():
    """Start background thread for database health checks and maintenance"""
    def watcher():
        while True:
            try:
                # Check connection health
                if not check_db_health():
                    logger.error("Database health check failed in watcher")
                
                # Run maintenance every hour
                if time.time() % 3600 < 60:  # Roughly every hour
                    run_maintenance()
                
                # Log pool stats every 5 minutes
                if time.time() % 300 < 60:
                    stats = get_pool_stats()
                    logger.info(f"Connection pool stats: {stats}")
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Database watcher error: {e}")
                time.sleep(60)
    
    # Start the watcher in a daemon thread
    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    return thread

# Initialize database with optional sample data
def init_db(create_sample_data=False):
    """Initialize database tables and optionally create sample data"""
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        if create_sample_data:
            from .sample_data import create_sample_data
            create_sample_data()
            logger.info("Sample data created successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Database connection info endpoint
def get_db_info():
    """Get database information for status endpoints"""
    return {
        "url": DATABASE_URL.split('@')[-1] if DATABASE_URL else "unknown",  # Hide credentials
        "pool_stats": get_pool_stats(),
        "version": get_db_version(),
        "healthy": check_db_health(),
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW
    }

# Start the database watcher when module is imported
if os.getenv("START_DB_WATCHER", "true").lower() == "true":
    start_db_watcher()
    logger.info("Database watcher started")

# Log database configuration at startup
logger.info(f"Database configuration: pool_size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}, "
            f"pool_timeout={POOL_TIMEOUT}, pool_recycle={POOL_RECYCLE}, pre_ping={POOL_PRE_PING}")

# Export connection health for health checks
db_health_status = check_db_health()
if not db_health_status:
    logger.warning("Initial database health check failed")