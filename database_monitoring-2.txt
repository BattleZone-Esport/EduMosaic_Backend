import time
import logging
from datetime import datetime
import sentry_sdk
from database import engine, db_metrics
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DatabaseError

# Setup logging
logger = logging.getLogger("database-monitor")

# Initialize Sentry for this module too (if not already done globally)
# This ensures even if main app crashes, this module can still report DB issues
try:
    # Only initialize if SENTRY_DSN is present
    if sentry_sdk.Hub.current.client is None and os.getenv("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production")
        )
except Exception:
    pass  # If Sentry init fails, continue gracefully

class DatabaseMonitor:
    def __init__(self):
        self.last_check = datetime.now()
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5  # After 5 failures, trigger critical alert

    def monitor_connection_pool(self):
        """Monitor database connection pool health with retry & error handling"""
        try:
            with engine.connect() as conn:
                result = conn.execute("""
                    SELECT 
                        COUNT(*) as total_connections,
                        SUM(CASE WHEN state = 'active' THEN 1 ELSE 0 END) as active_connections,
                        SUM(CASE WHEN state = 'idle' THEN 1 ELSE 0 END) as idle_connections,
                        SUM(CASE WHEN state = 'idle in transaction' THEN 1 ELSE 0 END) as idle_in_transaction
                    FROM pg_stat_activity 
                    WHERE usename = CURRENT_USER
                """)
                stats = result.fetchone()
                
                total = stats[0] or 0
                active = stats[1] or 0
                idle = stats[2] or 0
                idle_txn = stats[3] or 0
                
                # Log healthy state
                logger.info(f"✅ DB Pool Health - Total: {total}, Active: {active}, Idle: {idle}, IdleTxn: {idle_txn}")
                
                # Alert if dangerous thresholds breached
                if active > 80:  # High active connections
                    logger.warning(f"⚠️ High Active Connections: {active}/80 threshold")
                    sentry_sdk.capture_message(f"High DB Active Connections: {active}", level="warning")
                
                if idle_txn > 5:  # Long-running transactions blocking others
                    logger.warning(f"⚠️ {idle_txn} idle-in-transaction connections detected!")
                    sentry_sdk.capture_message(f"{idle_txn} idle-in-transaction connections found", level="warning")
                
                # Reset failure counter on success
                self.consecutive_failures = 0
                
        except (OperationalError, DatabaseError, SQLAlchemyError) as e:
            error_msg = f"❌ Connection Pool Monitoring Failed: {str(e)}"
            logger.error(error_msg)
            self.consecutive_failures += 1
            
            # Critical alert after multiple failures
            if self.consecutive_failures >= self.max_consecutive_failures:
                sentry_sdk.capture_message(
                    f"CRITICAL: Database connection pool failed {self.max_consecutive_failures} times consecutively!",
                    level="error"
                )
                logger.critical(f"🚨 CRITICAL: DB connection pool down for {self.max_consecutive_failures} checks!")
            
            # Also capture the exception in Sentry
            sentry_sdk.capture_exception(e)
            
        except Exception as e:
            error_msg = f"❌ Unexpected error in monitor_connection_pool: {str(e)}"
            logger.error(error_msg)
            sentry_sdk.capture_exception(e)

    def check_query_performance(self):
        """Check for slow queries (>5s) and long-running transactions"""
        try:
            with engine.connect() as conn:
                result = conn.execute("""
                    SELECT 
                        pid, 
                        now() - query_start as duration, 
                        query,
                        state
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                      AND now() - query_start > interval '5 seconds'
                      AND query NOT LIKE '%pg_stat_activity%'  -- Exclude monitoring queries
                    ORDER BY duration DESC
                    LIMIT 10
                """)
                slow_queries = result.fetchall()

                if slow_queries:
                    for idx, query in enumerate(slow_queries, 1):
                        pid = query[0]
                        duration = query[1]
                        sql = str(query[2])[:200] + "..." if len(str(query[2])) > 200 else str(query[2])
                        state = query[3]
                        
                        log_msg = f"🔍 Slow Query #{idx}: PID={pid}, Duration={duration}, State={state}, Query={sql}"
                        logger.warning(log_msg)
                        
                        # Send to Sentry for alerting
                        sentry_sdk.capture_message(
                            f"Slow Query Detected: PID {pid} ({duration}) - {sql}",
                            level="warning"
                        )

                    # If more than 3 slow queries, trigger high priority alert
                    if len(slow_queries) >= 3:
                        sentry_sdk.capture_message(
                            f"CRITICAL: {len(slow_queries)} slow queries detected simultaneously!",
                            level="error"
                        )
                        logger.critical(f"🚨 CRITICAL: {len(slow_queries)} slow queries running at once!")

                # Reset on success
                self.consecutive_failures = 0

        except (OperationalError, DatabaseError, SQLAlchemyError) as e:
            error_msg = f"❌ Slow Query Check Failed: {str(e)}"
            logger.error(error_msg)
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                sentry_sdk.capture_message(
                    f"CRITICAL: Slow query monitoring failed {self.max_consecutive_failures} times!",
                    level="error"
                )
                logger.critical("🚨 CRITICAL: Slow query monitoring system down!")
            sentry_sdk.capture_exception(e)
        except Exception as e:
            error_msg = f"❌ Unexpected error in check_query_performance: {str(e)}"
            logger.error(error_msg)
            sentry_sdk.capture_exception(e)

    def check_database_health(self):
        """Basic health ping — should be fast and reliable"""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"❌ Database health ping failed: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False

    def run_monitoring(self):
        """Main monitoring loop — runs every 5 minutes"""
        start_time = time.time()
        
        try:
            logger.info("🔄 Starting database monitoring cycle...")
            
            # Run all checks
            self.monitor_connection_pool()
            self.check_query_performance()
            health = self.check_database_health()
            
            # Update metrics
            if health:
                db_metrics.increment_connections()
            else:
                db_metrics.increment_failed_connections()

            # Log execution time
            duration = time.time() - start_time
            logger.info(f"✅ Database monitoring completed in {duration:.2f}s")

        except Exception as e:
            # This catches ANY unhandled exception in the entire monitoring task
            error_msg = f"❌ FATAL: Database monitoring task crashed unexpectedly: {str(e)}"
            logger.critical(error_msg, exc_info=True)
            sentry_sdk.capture_exception(e)
            # Don't let one crash kill the whole background process — it will retry in 5 min