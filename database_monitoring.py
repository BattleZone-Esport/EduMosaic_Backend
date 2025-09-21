import time
import os
import logging
from datetime import datetime, timedelta
import sentry_sdk
from database import engine, db_metrics, SessionLocal
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DatabaseError
import asyncio
import psutil
from typing import Dict, Any, List, Optional

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
            environment=os.getenv("ENVIRONMENT", "production"),
            # Add more context for database monitoring
            _experiments={"record_sql_params": False}  # Don't record SQL parameters for security
        )
        logger.info("✅ Sentry initialized for database monitoring")
except Exception as e:
    logger.error(f"❌ Failed to initialize Sentry in database monitoring: {e}")
    # Continue without Sentry if initialization fails

class DatabaseMonitor:
    def __init__(self):
        self.last_check = datetime.now()
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5  # After 5 failures, trigger critical alert
        self.metrics_history: List[Dict[str, Any]] = []
        self.max_history_size = 100  # Keep last 100 metrics readings
        self.last_metrics_report = datetime.now()

    def monitor_connection_pool(self):
        """Monitor database connection pool health with retry & error handling"""
        try:
            with engine.connect() as conn:
                # Use text() for SQL compatibility with psycopg3
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as total_connections,
                        SUM(CASE WHEN state = 'active' THEN 1 ELSE 0 END) as active_connections,
                        SUM(CASE WHEN state = 'idle' THEN 1 ELSE 0 END) as idle_connections,
                        SUM(CASE WHEN state = 'idle in transaction' THEN 1 ELSE 0 END) as idle_in_transaction,
                        SUM(CASE WHEN state = 'idle in transaction (aborted)' THEN 1 ELSE 0 END) as idle_in_transaction_aborted,
                        SUM(CASE WHEN state = 'fastpath function call' THEN 1 ELSE 0 END) as fastpath_function_call,
                        SUM(CASE WHEN state = 'disabled' THEN 1 ELSE 0 END) as disabled_connections
                    FROM pg_stat_activity 
                    WHERE usename = CURRENT_USER OR usename IS NULL
                """))
                stats = result.fetchone()
                
                total = stats[0] or 0
                active = stats[1] or 0
                idle = stats[2] or 0
                idle_txn = stats[3] or 0
                idle_txn_aborted = stats[4] or 0
                fastpath = stats[5] or 0
                disabled = stats[6] or 0
                
                # Log healthy state with more details
                logger.info(f"✅ DB Pool Health - Total: {total}, Active: {active}, Idle: {idle}, "
                           f"IdleTxn: {idle_txn}, IdleTxnAborted: {idle_txn_aborted}, "
                           f"Fastpath: {fastpath}, Disabled: {disabled}")
                
                # Store metrics for trend analysis
                metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "total_connections": total,
                    "active_connections": active,
                    "idle_connections": idle,
                    "idle_in_transaction": idle_txn,
                    "idle_in_transaction_aborted": idle_txn_aborted,
                    "fastpath_function_call": fastpath,
                    "disabled_connections": disabled
                }
                self.metrics_history.append(metrics)
                # Keep history size manageable
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # Alert if dangerous thresholds breached
                if active > 80:  # High active connections
                    logger.warning(f"⚠️ High Active Connections: {active}/80 threshold")
                    sentry_sdk.capture_message(
                        f"High DB Active Connections: {active} (Threshold: 80)", 
                        level="warning",
                        contexts={"database": metrics}
                    )
                
                if idle_txn > 5:  # Long-running transactions blocking others
                    logger.warning(f"⚠️ {idle_txn} idle-in-transaction connections detected!")
                    sentry_sdk.capture_message(
                        f"{idle_txn} idle-in-transaction connections found", 
                        level="warning",
                        contexts={"database": metrics}
                    )
                
                if idle_txn_aborted > 0:  # Aborted transactions - critical issue
                    logger.error(f"🚨 {idle_txn_aborted} aborted transactions detected!")
                    sentry_sdk.capture_message(
                        f"CRITICAL: {idle_txn_aborted} aborted transactions found", 
                        level="error",
                        contexts={"database": metrics}
                    )
                
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
                # Use text() for SQL compatibility
                result = conn.execute(text("""
                    SELECT 
                        pid, 
                        now() - query_start as duration, 
                        query,
                        state,
                        application_name,
                        client_addr,
                        usename,
                        datname
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                      AND now() - query_start > interval '5 seconds'
                      AND query NOT LIKE '%pg_stat_activity%'  -- Exclude monitoring queries
                    ORDER BY duration DESC
                    LIMIT 15
                """))
                slow_queries = result.fetchall()

                if slow_queries:
                    for idx, query in enumerate(slow_queries, 1):
                        pid = query[0]
                        duration = query[1]
                        sql = str(query[2])[:500] + "..." if len(str(query[2])) > 500 else str(query[2])
                        state = query[3]
                        app_name = query[4] or "unknown"
                        client_addr = query[5] or "unknown"
                        username = query[6] or "unknown"
                        db_name = query[7] or "unknown"
                        
                        log_msg = (f"🔍 Slow Query #{idx}: PID={pid}, Duration={duration}, "
                                  f"State={state}, DB={db_name}, User={username}, "
                                  f"App={app_name}, Client={client_addr}")
                        logger.warning(log_msg)
                        
                        # Send to Sentry for alerting with more context
                        sentry_sdk.capture_message(
                            f"Slow Query Detected: PID {pid} ({duration}) - {app_name}",
                            level="warning",
                            contexts={
                                "query": {
                                    "pid": pid,
                                    "duration": str(duration),
                                    "state": state,
                                    "database": db_name,
                                    "user": username,
                                    "application": app_name,
                                    "client": client_addr,
                                    "query_preview": sql[:200] + "..." if len(sql) > 200 else sql
                                }
                            }
                        )

                    # If more than 3 slow queries, trigger high priority alert
                    if len(slow_queries) >= 3:
                        sentry_sdk.capture_message(
                            f"CRITICAL: {len(slow_queries)} slow queries detected simultaneously!",
                            level="error",
                            contexts={"count": len(slow_queries)}
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

    def check_database_size(self):
        """Monitor database size and growth trends"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        pg_database_size(current_database()) as total_size,
                        pg_size_pretty(pg_database_size(current_database())) as total_size_pretty,
                        (SELECT pg_size_pretty(sum(pg_relation_size(oid))) 
                         FROM pg_class WHERE relkind IN ('r', 't')) as table_size,
                        (SELECT pg_size_pretty(sum(pg_relation_size(oid))) 
                         FROM pg_class WHERE relkind = 'i') as index_size
                """))
                size_info = result.fetchone()
                
                total_size = size_info[0] or 0
                total_size_pretty = size_info[1] or "0 bytes"
                table_size = size_info[2] or "0 bytes"
                index_size = size_info[3] or "0 bytes"
                
                logger.info(f"💾 Database Size: {total_size_pretty} (Tables: {table_size}, Indexes: {index_size})")
                
                # Alert if database is growing too large
                if total_size > 10 * 1024 * 1024 * 1024:  # 10GB threshold
                    logger.warning(f"⚠️ Database size exceeds 10GB: {total_size_pretty}")
                    sentry_sdk.capture_message(
                        f"Database size warning: {total_size_pretty}",
                        level="warning",
                        contexts={
                            "database_size": {
                                "total_bytes": total_size,
                                "total_human": total_size_pretty,
                                "table_size": table_size,
                                "index_size": index_size
                            }
                        }
                    )
                
        except Exception as e:
            logger.error(f"❌ Database size check failed: {str(e)}")
            # Don't capture in Sentry as this is a non-critical check

    def check_index_usage(self):
        """Monitor index usage and identify unused indexes"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        schemaname,
                        relname,
                        indexrelname,
                        idx_scan,
                        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                    FROM pg_stat_all_indexes 
                    WHERE idx_scan = 0 
                    AND schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY pg_relation_size(indexrelid) DESC
                    LIMIT 10
                """))
                unused_indexes = result.fetchall()
                
                if unused_indexes:
                    logger.warning(f"🔍 Found {len(unused_indexes)} unused indexes")
                    for idx in unused_indexes:
                        logger.warning(f"   - {idx[0]}.{idx[1]}.{idx[2]} (Size: {idx[4]}, Scans: {idx[3]})")
                    
                    # Report to Sentry if many large unused indexes
                    large_unused = [idx for idx in unused_indexes if idx[4] and 'MB' in idx[4] or 'GB' in idx[4]]
                    if large_unused:
                        sentry_sdk.capture_message(
                            f"Found {len(large_unused)} large unused indexes",
                            level="info",
                            contexts={"unused_indexes": [
                                {
                                    "schema": idx[0],
                                    "table": idx[1],
                                    "index": idx[2],
                                    "scans": idx[3],
                                    "size": idx[4]
                                } for idx in large_unused
                            ]}
                        )
                
        except Exception as e:
            logger.error(f"❌ Index usage check failed: {str(e)}")
            # Don't capture in Sentry as this is a non-critical check

    def check_database_health(self):
        """Basic health ping — should be fast and reliable"""
        try:
            start_time = time.time()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            response_time = (time.time() - start_time) * 1000  # ms
            
            logger.info(f"✅ Database health check passed in {response_time:.2f}ms")
            
            # Track response time metrics
            db_metrics.increment_query_time(response_time / 1000)  # Convert to seconds
            
            # Alert if response time is too slow
            if response_time > 1000:  # 1 second threshold
                logger.warning(f"⚠️ Slow database response: {response_time:.2f}ms")
                sentry_sdk.capture_message(
                    f"Slow database response time: {response_time:.2f}ms",
                    level="warning"
                )
                
            return True, response_time
            
        except Exception as e:
            logger.error(f"❌ Database health ping failed: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False, 0

    def report_metrics_to_redis(self):
        """Report database metrics to Redis for external monitoring"""
        try:
            # Get current metrics
            metrics = db_metrics.get_status()
            
            # Add timestamp
            metrics["timestamp"] = datetime.utcnow().isoformat()
            metrics["metrics_history_count"] = len(self.metrics_history)
            
            # Report to Redis if it's been more than 1 minute since last report
            if (datetime.now() - self.last_metrics_report).total_seconds() > 60:
                async def async_report():
                    try:
                        from database import get_redis_pool
                        r = await get_redis_pool()
                        await r.hset("db_monitoring_metrics", mapping=metrics)
                        await r.expire("db_monitoring_metrics", 120)  # Expire after 2 minutes
                    except Exception as e:
                        logger.error(f"❌ Failed to report metrics to Redis: {e}")
                
                # Run async task
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(async_report())
                loop.close()
                
                self.last_metrics_report = datetime.now()
                logger.debug("✅ Database metrics reported to Redis")
                
        except Exception as e:
            logger.error(f"❌ Metrics reporting failed: {str(e)}")

    def run_monitoring(self):
        """Main monitoring loop — runs every 5 minutes"""
        start_time = time.time()
        
        try:
            logger.info("🔄 Starting database monitoring cycle...")
            
            # Run all checks
            self.monitor_connection_pool()
            self.check_query_performance()
            health, response_time = self.check_database_health()
            
            # Run additional checks less frequently (every 30 minutes)
            current_time = datetime.now()
            if current_time.minute % 30 == 0:  # Run every 30 minutes
                self.check_database_size()
                self.check_index_usage()
            
            # Update metrics
            if health:
                db_metrics.increment_connections()
            else:
                db_metrics.increment_failed_connections()

            # Report metrics to Redis
            self.report_metrics_to_redis()

            # Log execution time
            duration = time.time() - start_time
            logger.info(f"✅ Database monitoring completed in {duration:.2f}s")

        except Exception as e:
            # This catches ANY unhandled exception in the entire monitoring task
            error_msg = f"❌ FATAL: Database monitoring task crashed unexpectedly: {str(e)}"
            logger.critical(error_msg, exc_info=True)
            sentry_sdk.capture_exception(e)
            # Don't let one crash kill the whole background process — it will retry in 5 min

    def get_status_report(self) -> Dict[str, Any]:
        """Get a comprehensive status report of database health"""
        return {
            "last_check": self.last_check.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "metrics_history_count": len(self.metrics_history),
            "database_metrics": db_metrics.get_status(),
            "system_metrics": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent if os.path.exists('/') else 0
            }
        }

# Global monitor instance
db_monitor = DatabaseMonitor()

# Async version for modern Python applications
async def run_async_monitoring(interval_minutes: int = 5):
    """Run database monitoring in an async loop"""
    monitor = DatabaseMonitor()
    while True:
        try:
            # Run monitoring in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, monitor.run_monitoring)
            await asyncio.sleep(interval_minutes * 60)
        except Exception as e:
            logger.error(f"❌ Async monitoring task failed: {e}")
            sentry_sdk.capture_exception(e)
            await asyncio.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    # Run directly for testing
    logging.basicConfig(level=logging.INFO)
    monitor = DatabaseMonitor()
    monitor.run_monitoring()