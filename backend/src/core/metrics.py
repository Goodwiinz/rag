"""
Core metrics utilities for request tracking.

Provides simple metric recording functions for health checks and API endpoints.
Can be extended to integrate with Prometheus, OpenTelemetry, or other metrics backends.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# In-memory metrics storage (for development/testing)
# In production, replace with Prometheus/StatsD/OpenTelemetry integration
_request_counts: Dict[str, int] = {}
_request_durations: Dict[str, list] = {}


def record_request_count(
    endpoint: str,
    method: str = "GET",
    status_code: int = 200,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Record a request count metric.

    Args:
        endpoint: The API endpoint path
        method: HTTP method (GET, POST, etc.)
        status_code: HTTP response status code
        labels: Additional labels/tags for the metric
    """
    try:
        key = f"{method}:{endpoint}:{status_code}"
        if key not in _request_counts:
            _request_counts[key] = 0
        _request_counts[key] += 1

        # Log at debug level for tracking without user-provided values
        logger.debug("Request count recorded: %s", _request_counts[key])
    except Exception as e:
        # Metrics should never break the application
        logger.warning(f"Failed to record request count: {e}")


def record_request_duration(
    endpoint: str,
    duration_ms: float,
    method: str = "GET",
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Record a request duration metric.

    Args:
        endpoint: The API endpoint path
        duration_ms: Request duration in milliseconds
        method: HTTP method (GET, POST, etc.)
        labels: Additional labels/tags for the metric
    """
    try:
        key = f"{method}:{endpoint}"
        if key not in _request_durations:
            _request_durations[key] = []

        # Keep last 1000 measurements for averaging
        _request_durations[key].append(duration_ms)
        if len(_request_durations[key]) > 1000:
            _request_durations[key] = _request_durations[key][-1000:]

        logger.debug("Request duration recorded: %.2fms", duration_ms)
    except Exception as e:
        # Metrics should never break the application
        logger.warning(f"Failed to record request duration: {e}")


@contextmanager
def track_request_duration(endpoint: str, method: str = "GET"):
    """
    Context manager to track request duration.

    Usage:
        with track_request_duration("/api/health", "GET"):
            # do work
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        record_request_duration(endpoint, duration_ms, method)


def metrics_decorator(endpoint: str, method: str = "GET"):
    """
    Decorator to automatically track request count and duration.

    Usage:
        @metrics_decorator("/api/health", "GET")
        async def health_check():
            return {"status": "ok"}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                record_request_count(endpoint, method, status_code)
                record_request_duration(endpoint, duration_ms, method)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                record_request_count(endpoint, method, status_code)
                record_request_duration(endpoint, duration_ms, method)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of all recorded metrics.

    Returns:
        Dictionary containing counts and average durations
    """
    summary = {
        "request_counts": dict(_request_counts),
        "average_durations": {},
    }

    for key, durations in _request_durations.items():
        if durations:
            summary["average_durations"][key] = {
                "avg_ms": sum(durations) / len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "count": len(durations),
            }

    return summary


def reset_metrics() -> None:
    """Reset all metrics (useful for testing)."""
    global _request_counts, _request_durations
    _request_counts = {}
    _request_durations = {}
