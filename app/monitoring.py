"""
Application monitoring and performance tracking
"""
import time
from datetime import datetime
from functools import wraps
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor application performance metrics"""

    def __init__(self):
        self.metrics = {
            "api_calls": 0,
            "api_errors": 0,
            "db_queries": 0,
            "avg_response_time": 0.0,
            "peak_memory": 0.0,
        }
        self.request_times = []

    def track_request(self, func: Callable) -> Callable:
        """Decorator to track request performance"""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                self.metrics["api_calls"] += 1
                return result
            except Exception as e:
                self.metrics["api_errors"] += 1
                logger.error(f"API error in {func.__name__}: {e}")
                raise
            finally:
                elapsed = time.time() - start_time
                self.request_times.append(elapsed)
                if len(self.request_times) > 1000:
                    self.request_times.pop(0)
                self.metrics["avg_response_time"] = sum(self.request_times) / len(self.request_times)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                self.metrics["api_calls"] += 1
                return result
            except Exception as e:
                self.metrics["api_errors"] += 1
                logger.error(f"API error in {func.__name__}: {e}")
                raise
            finally:
                elapsed = time.time() - start_time
                self.request_times.append(elapsed)
                if len(self.request_times) > 1000:
                    self.request_times.pop(0)
                self.metrics["avg_response_time"] = sum(self.request_times) / len(self.request_times)

        # Check if coroutine
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def get_metrics(self) -> dict:
        """Get current metrics"""
        return {
            **self.metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def log_slow_query(self, query: str, duration: float, threshold: float = 0.5):
        """Log slow database queries"""
        if duration > threshold:
            logger.warning(f"Slow query ({duration:.2f}s): {query[:100]}...")

    def log_error(self, error_type: str, error_msg: str, context: dict = None):
        """Log application errors"""
        logger.error(f"{error_type}: {error_msg}", extra=context or {})


# Global monitor instance
monitor = PerformanceMonitor()


class CircuitBreaker:
    """Circuit breaker pattern for external service calls"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker"""
        if self.state == "open":
            if (time.time() - self.last_failure_time) > self.timeout:
                self.state = "half-open"
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            raise e


class HealthChecker:
    """Application health checks"""

    def __init__(self, db_session=None):
        self.db_session = db_session
        self.health_status = {
            "database": "unknown",
            "cache": "unknown",
            "api": "ok",
        }

    def check_database(self) -> bool:
        """Check database connectivity"""
        try:
            if self.db_session:
                self.db_session.execute("SELECT 1")
                self.health_status["database"] = "ok"
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.health_status["database"] = "error"
            return False

    def check_cache(self, redis_client=None) -> bool:
        """Check Redis cache connectivity"""
        try:
            if redis_client:
                redis_client.ping()
                self.health_status["cache"] = "ok"
                return True
            return True
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            self.health_status["cache"] = "error"
            return False

    def get_health_status(self) -> dict:
        """Get overall health status"""
        return {
            "status": "healthy" if all(v == "ok" for v in self.health_status.values()) else "degraded",
            "components": self.health_status,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Health checker instance
health_checker = HealthChecker()
