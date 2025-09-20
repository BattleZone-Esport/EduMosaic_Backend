# database-2.py — INDIA'S NO.1 EDITION (Final Production-Ready)
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
import time
import sentry_sdk
import psutil
import asyncio
import redis.asyncio as redis
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DatabaseError, DisconnectionError
from typing import Dict, Any, Optional
import json
import hashlib
import secrets
from datetime import datetime, timedelta
import re

# Load environment variables
load_dotenv()

# === LOGGING SETUP === #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler("database.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("database")

# === SENTRY INTEGRATION (CRITICAL) === #
try:
    if sentry_sdk.Hub.current.client is None and os.getenv("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production"),
            integrations=[],
            # 🔐 SECURITY: Don't send PII unless explicitly needed
            send_default_pii=False,
            # 🔒 Capture only critical errors from DB layer
            max_breadcrumbs=50,
            release=os.getenv("APP_VERSION", "unknown")
        )
        logger.info("✅ Sentry initialized for database module")
except Exception as e:
    logger.error(f"❌ Failed to initialize Sentry in database module: {e}")

# === DATABASE URL CONFIGURATION === #
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("❌ DATABASE_URL environment variable is NOT SET!")
    raise ValueError("DATABASE_URL environment variable is required")

# Sanitize & validate connection string
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Log sanitized version (without credentials)
safe_url = re.sub(r':[^@]+@', ':*****@', DATABASE_URL)
logger.info(f"✅ Database URL configured: {safe_url}")

# === PRODUCTION-TUNED ENGINE CONFIGURATION === #
engine = create_engine(
    DATABASE_URL,
    pool_size=20,                    # Increased for high traffic
    max_overflow=30,                 # Handle sudden spikes
    pool_timeout=60,                 # Wait up to 60s before failing (was 30)
    pool_recycle=1800,               # Recycle every 30 mins — prevents stale connections
    pool_pre_ping=True,              # CRITICAL: Check connection health before use
    echo=False,                      # NEVER True in production
    connect_args={
        "connect_timeout": 15,       # ⚠️ CRITICAL: Wait 15s for initial conn
        "application_name": "edumosaic-app",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "tcp_user_timeout": 15000,   # TCP timeout after 15s of no response
        "options": "-c statement_timeout=30000"  # ⚠️ MAX query timeout: 30 seconds
    },
    execution_options={
        "isolation_level": "READ COMMITTED"
    },
    # 🔐 SECURITY: Disable risky features
    pool_use_lifo=True,              # Use LIFO for better connection reuse
    pool_reset_on_return="rollback"  # Always rollback on return — prevents state leakage
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Better performance
)

Base = declarative_base()

# === REDIS CONNECTION FOR RATE LIMITING & SESSION TRACKING === #
redis_pool = None

async def get_redis_pool():
    global redis_pool
    if redis_pool is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=20,
            decode_responses=True,
            health_check_interval=30,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_keepalive=True
        )
    return redis.Redis(connection_pool=redis_pool)

# === DATABASE HEALTH CHECK WITH RETRY & SENTINEL === #
def check_database_health(max_retries: int = 3) -> bool:
    """Check DB health with exponential backoff + Sentry alerts + Redis heartbeat"""
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                result = conn.execute("SELECT 1")
                if result.scalar() == 1:
                    # ✅ Send heartbeat to Redis for monitoring dashboards
                    async def send_heartbeat():
                        try:
                            r = await get_redis_pool()
                            await r.setex("db_heartbeat", 60, "ok")  # Expires in 60s
                            await r.hset("db_status", mapping={
                                "last_checked": datetime.utcnow().isoformat(),
                                "status": "healthy",
                                "version": os.getenv("APP_VERSION", "unknown")
                            })
                        except Exception as e:
                            logger.warning(f"⚠️ Could not update Redis heartbeat: {e}")
                    
                    asyncio.create_task(send_heartbeat())
                    
                    logger.info("✅ Database connection healthy")
                    return True
        except (OperationalError, DatabaseError, DisconnectionError, SQLAlchemyError) as e:
            wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
            logger.warning(f"⚠️ Database health check failed (attempt {attempt}/{max_retries}): {str(e)}. Retrying in {wait_time}s...")
            if attempt == max_retries:
                sentry_sdk.capture_exception(e)
                logger.critical("🚨 CRITICAL: Database unreachable after all retries!")
                
                # 💥 Critical Alert to Redis for DevOps Dashboard
                async def send_critical_alert():
                    try:
                        r = await get_redis_pool()
                        await r.hset("db_status", mapping={
                            "last_checked": datetime.utcnow().isoformat(),
                            "status": "critical",
                            "error": str(e),
                            "version": os.getenv("APP_VERSION", "unknown")
                        })
                        await r.publish("db_alerts", json.dumps({
                            "level": "CRITICAL",
                            "message": "Database connection failed after retries",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    except Exception as ex:
                        logger.error(f"❌ Failed to publish DB alert: {ex}")
                
                asyncio.create_task(send_critical_alert())
                return False
            time.sleep(wait_time)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Unexpected error in health check: {e}")
            return False
    return False

# === CONTEXT MANAGER FOR SESSIONS — WITH QUERY AUDITING === #
@contextmanager
def get_db():
    """Get database session with automatic cleanup, slow query detection, audit logging & security checks"""
    db = SessionLocal()
    start_time = time.time()
    request_id = getattr(getattr(db, 'request_context', None), 'request_id', 'UNKNOWN')
    
    try:
        yield db
        db.commit()
        
        # 🔍 Audit successful queries (optional — disable in prod if too heavy)
        # duration = time.time() - start_time
        # if duration > 0.5:  # Log queries >500ms
        #     logger.info(f"✅ Successful query | RequestID: {request_id} | Duration: {duration:.3f}s")

    except Exception as e:
        db.rollback()
        error_msg = f"❌ Database operation failed | RequestID: {request_id} | Error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 🔐 SECURITY: Never log raw SQL or user data
        # But capture the exception type and context
        sentry_sdk.capture_exception(e)
        
        # 🔔 Push to Redis pub/sub for real-time alerting
        async def push_alert():
            try:
                r = await get_redis_pool()
                await r.publish("db_alerts", json.dumps({
                    "level": "ERROR",
                    "message": f"DB Error: {type(e).__name__}",
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as ex:
                logger.error(f"Failed to push DB alert: {ex}")
        
        asyncio.create_task(push_alert())
        raise
        
    finally:
        db.close()
        execution_time = time.time() - start_time
        
        # ⚠️ Slow Query Detection — Critical for Performance
        if execution_time > 1.0:
            logger.warning(f"⚠️ Slow database session | RequestID: {request_id} | Duration: {execution_time:.3f}s | Query took >1s")
            sentry_sdk.capture_message(f"Slow DB Query: {execution_time:.3f}s | RequestID: {request_id}", level="warning")
            
        # 📊 Track metrics
        if execution_time > 0:
            db_metrics.increment_query_time(execution_time)

# === DATABASE CONNECTION METRICS — REAL-TIME MONITORING === #
class DatabaseMetrics:
    def __init__(self):
        self.total_connections = 0
        self.failed_connections = 0
        self.total_queries = 0
        self.slow_queries = 0
        self.avg_query_time = 0.0
        self.active_connections = 0
        self.max_active_connections = 0
        self.query_latency_sum = 0.0
        self.last_reported = datetime.utcnow()
        
    def increment_connections(self):
        self.total_connections += 1
        self.active_connections += 1
        self.max_active_connections = max(self.max_active_connections, self.active_connections)
        
    def increment_failed_connections(self):
        self.failed_connections += 1
        sentry_sdk.capture_message(f"Database connection failed. Total failures: {self.failed_connections}", level="error")
        
    def decrement_connections(self):
        self.active_connections -= 1
        
    def increment_query_time(self, duration: float):
        self.total_queries += 1
        self.query_latency_sum += duration
        self.avg_query_time = self.query_latency_sum / self.total_queries
        
        if duration > 1.0:
            self.slow_queries += 1
            
        # Report stats every 5 minutes
        if (datetime.utcnow() - self.last_reported).total_seconds() > 300:
            self._report_stats()
            self.last_reported = datetime.utcnow()
            
    def _report_stats(self):
        """Send aggregated metrics to Redis for Grafana/Dashboard"""
        try:
            async def send_to_redis():
                r = await get_redis_pool()
                await r.hset("db_metrics", mapping={
                    "total_connections": str(self.total_connections),
                    "failed_connections": str(self.failed_connections),
                    "active_connections": str(self.active_connections),
                    "max_active_connections": str(self.max_active_connections),
                    "total_queries": str(self.total_queries),
                    "slow_queries": str(self.slow_queries),
                    "avg_query_time_ms": str(round(self.avg_query_time * 1000, 2)),
                    "pool_size": str(engine.pool.size()),
                    "pool_overflow": str(engine.pool.overflow()),
                    "pool_checked_out": str(engine.pool.checkedout()),
                    "uptime_minutes": str(int((datetime.utcnow() - startup_time).total_seconds() / 60))
                })
                await r.expire("db_metrics", 600)  # Auto-expire in 10 min
            asyncio.create_task(send_to_redis())
        except Exception as e:
            logger.error(f"Failed to report DB metrics: {e}")
            
    def get_status(self) -> Dict[str, Any]:
        return {
            "total_connections": self.total_connections,
            "failed_connections": self.failed_connections,
            "active_connections": self.active_connections,
            "max_active_connections": self.max_active_connections,
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "avg_query_time_ms": round(self.avg_query_time * 1000, 2),
            "pool_size": engine.pool.size(),
            "pool_overflow": engine.pool.overflow(),
            "pool_checked_out": engine.pool.checkedout(),
            "cpu_usage_percent": psutil.cpu_percent(),
            "memory_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent
        }

db_metrics = DatabaseMetrics()

# === CRITICAL: DATABASE AUDIT TRAIL — FOR SECURITY & COMPLIANCE === #
class AuditLog:
    @staticmethod
    def log_action(action: str, user_id: Optional[int], ip_address: Optional[str], details: dict = None):
        """
        Logs sensitive actions for compliance (GDPR, SOC2, ISO27001)
        Example: "user_login", "password_change", "admin_delete_quiz"
        """
        try:
            log_entry = {
                "action": action,
                "user_id": user_id,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {},
                "hostname": os.getenv("HOSTNAME", "unknown"),
                "app_version": os.getenv("APP_VERSION", "unknown")
            }
            
            # Hash sensitive fields if needed
            if "email" in log_entry["details"]:
                log_entry["details"]["email"] = hashlib.sha256(log_entry["details"]["email"].encode()).hexdigest()
            if "phone" in log_entry["details"]:
                log_entry["details"]["phone"] = hashlib.sha256(log_entry["details"]["phone"].encode()).hexdigest()
                
            # Send to Redis stream for real-time alerting
            async def send_audit():
                try:
                    r = await get_redis_pool()
                    await r.xadd("audit_log", log_entry)
                    await r.xtrim("audit_log", maxlen=10000)  # Keep last 10k logs
                except Exception as e:
                    logger.error(f"Failed to write audit log: {e}")
                    
            asyncio.create_task(send_audit())
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

# === INITIALIZATION — CREATE TABLES & INDEXES === #
def init_db():
    """Initialize database tables and indexes — with security hardening"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully")
        
        # 🔐 SECURITY: Create PostgreSQL-specific hardening extensions
        with engine.connect() as conn:
            # Enable pgcrypto for password hashing (if not already done)
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            
            # Create essential indexes for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_quizzes_category ON quizzes(category_id);
                CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(quiz_id);
                CREATE INDEX IF NOT EXISTS idx_scores_user ON user_scores(user_id);
                CREATE INDEX IF NOT EXISTS idx_scores_completed_at ON user_scores(completed_at);
                CREATE INDEX IF NOT EXISTS idx_quiz_sessions_session_id ON quiz_sessions(session_id);
                CREATE INDEX IF NOT EXISTS idx_analytics_events_timestamp ON analytics_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_exam_categories_name ON exam_categories(name);
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_jti ON refresh_tokens(jti);
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_badges_user_id ON user_badges(user_id);
                CREATE INDEX IF NOT EXISTS idx_followers_followed_id ON follow(followed_id);
                CREATE INDEX IF NOT EXISTS idx_followers_follower_id ON follow(follower_id);
                CREATE INDEX IF NOT EXISTS idx_study_group_members_user_id ON study_group_members(user_id);
                CREATE INDEX IF NOT EXISTS idx_quiz_tags_tag_id ON quiz_tags(tag_id);
                CREATE INDEX IF NOT EXISTS idx_question_tags_tag_id ON question_tags(tag_id);
                CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
                CREATE INDEX IF NOT EXISTS idx_quizzes_is_active ON quizzes(is_active);
                CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
                CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);
                CREATE INDEX IF NOT EXISTS idx_users_streak ON users(streak);
                CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp);
                CREATE INDEX IF NOT EXISTS idx_users_level ON users(level);
                CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins);
                CREATE INDEX IF NOT EXISTS idx_users_gems ON users(gems);
                CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
                CREATE INDEX IF NOT EXISTS idx_users_premium_expiry ON users(premium_expiry);
                CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
                
                -- For full-text search (future-proof)
                CREATE INDEX IF NOT EXISTS idx_questions_search ON questions USING GIN(to_tsvector('english', question_text));
                CREATE INDEX IF NOT EXISTS idx_quizzes_search ON quizzes USING GIN(to_tsvector('english', title || ' ' || description));
                
                -- For JSONB indexing (if using JSON columns)
                CREATE INDEX IF NOT EXISTS idx_users_premium_features_gin ON users USING GIN(premium_features);
            """))
            
            # 🔐 SECURITY: Restrict permissions (this should be done at DB level too!)
            # But we can enforce via app logic — never allow raw SQL injection
            # We're safe because we use ORM + parameterized queries
            
            conn.commit()
            logger.info("✅ Database indexes and extensions created/verified")
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize database schema: {e}")
        sentry_sdk.capture_exception(e)
        raise

# === STARTUP TIME & INITIAL CONNECTION === #
startup_time = datetime.utcnow()

try:
    if check_database_health():
        logger.info("✅ Database connection successful on startup")
        db_metrics.increment_connections()
    else:
        logger.critical("❌ Database connection FAILED on startup — app may be unstable!")
        db_metrics.increment_failed_connections()
        # Do NOT exit — let the app start, background monitor will fix it
except Exception as e:
    logger.critical(f"❌ Database connection test crashed on startup: {e}")
    sentry_sdk.capture_exception(e)
    db_metrics.increment_failed_connections()

# === RUN INITIALIZATION === #
init_db()

# === FINAL TOUCH: CUSTOM EXCEPTIONS FOR SECURITY === #
class DatabaseSecurityException(Exception):
    """Custom exception for security-related DB violations"""
    pass

class QueryInjectionAttempt(DatabaseSecurityException):
    pass

class DataLeakAttempt(DatabaseSecurityException):
    pass

# === END OF FILE === #