"""
Query Monitoring Middleware

Monitors database queries for performance issues:
- Tracks slow queries
- Detects N+1 query problems
- Logs query statistics per request
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("query_monitor")

# Context variable to track queries per request
request_query_context: ContextVar[Optional["RequestQueryStats"]] = ContextVar(
    "request_query_context", default=None
)


@dataclass
class QueryInfo:
    """Information about a single query."""

    statement: str
    duration_ms: float
    parameters: Optional[dict] = None


@dataclass
class RequestQueryStats:
    """Query statistics for a single request."""

    request_path: str
    request_method: str
    queries: list[QueryInfo] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def query_count(self) -> int:
        return len(self.queries)

    @property
    def total_query_time_ms(self) -> float:
        return sum(q.duration_ms for q in self.queries)

    @property
    def slow_queries(self) -> list[QueryInfo]:
        return [q for q in self.queries if q.duration_ms > 100]

    def get_summary(self) -> dict:
        return {
            "path": self.request_path,
            "method": self.request_method,
            "query_count": self.query_count,
            "total_query_time_ms": round(self.total_query_time_ms, 2),
            "slow_query_count": len(self.slow_queries),
            "request_duration_ms": round((time.time() - self.start_time) * 1000, 2),
        }


class QueryMonitor:
    """
    Monitor database queries for performance issues.

    Configuration:
    - slow_query_threshold_ms: Queries taking longer than this are logged as slow
    - high_query_count_threshold: Requests with more queries than this trigger warnings
    - enable_parameter_logging: Whether to log query parameters (can expose sensitive data)
    """

    def __init__(
        self,
        slow_query_threshold_ms: float = 100.0,
        high_query_count_threshold: int = 10,
        enable_parameter_logging: bool = False,
    ):
        self.slow_query_threshold = slow_query_threshold_ms / 1000  # Convert to seconds
        self.high_query_count_threshold = high_query_count_threshold
        self.enable_parameter_logging = enable_parameter_logging
        self._registered = False

    def register_engine_events(self, engine: Engine) -> None:
        """Register SQLAlchemy event listeners on the engine."""
        if self._registered:
            return

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            conn.info.setdefault("query_start_times", []).append(time.time())

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            start_times = conn.info.get("query_start_times", [])
            if not start_times:
                return

            start_time = start_times.pop()
            duration = time.time() - start_time
            duration_ms = duration * 1000

            # Record query in request context if available
            ctx = request_query_context.get()
            if ctx:
                query_info = QueryInfo(
                    statement=statement[:500],  # Truncate long statements
                    duration_ms=duration_ms,
                    parameters=parameters if self.enable_parameter_logging else None,
                )
                ctx.queries.append(query_info)

            # Log slow queries
            if duration > self.slow_query_threshold:
                logger.warning(
                    f"Slow query ({duration_ms:.1f}ms): {statement[:200]}..."
                )

        self._registered = True

    def start_request(self, path: str, method: str) -> None:
        """Start tracking queries for a new request."""
        stats = RequestQueryStats(request_path=path, request_method=method)
        request_query_context.set(stats)

    def end_request(self) -> Optional[RequestQueryStats]:
        """
        End request tracking and return statistics.

        Logs warnings if thresholds are exceeded.
        """
        stats = request_query_context.get()
        if not stats:
            return None

        # Log warnings for potential issues
        if stats.query_count > self.high_query_count_threshold:
            logger.warning(
                f"High query count ({stats.query_count}) for "
                f"{stats.request_method} {stats.request_path} - "
                f"possible N+1 query problem"
            )

        if stats.slow_queries:
            logger.warning(
                f"{len(stats.slow_queries)} slow queries for "
                f"{stats.request_method} {stats.request_path}"
            )

        # Reset context
        request_query_context.set(None)

        return stats


# Global query monitor instance
query_monitor = QueryMonitor()


class QueryMonitorMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that monitors queries per request.

    Add to FastAPI app:
        app.add_middleware(QueryMonitorMiddleware)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip monitoring for health checks and static files
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        query_monitor.start_request(path=request.url.path, method=request.method)

        try:
            response = await call_next(request)
        finally:
            stats = query_monitor.end_request()
            if stats:
                # Add query stats to response headers (debug mode only)
                if response.headers.get("X-Debug-Mode"):
                    response.headers["X-Query-Count"] = str(stats.query_count)
                    response.headers["X-Query-Time-Ms"] = str(
                        round(stats.total_query_time_ms, 2)
                    )

        return response


def setup_query_monitoring(engine: Engine) -> None:
    """
    Set up query monitoring for the given engine.

    Call this during application startup:
        from src.core.database import engine
        from src.middleware.query_monitor import setup_query_monitoring
        setup_query_monitoring(engine)
    """
    query_monitor.register_engine_events(engine)
    logger.info("Query monitoring enabled")


def get_current_request_stats() -> Optional[RequestQueryStats]:
    """Get query statistics for the current request."""
    return request_query_context.get()
