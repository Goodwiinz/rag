"""
Lightweight compatibility metrics helpers for core health endpoints.

This module provides a stable import path (`src.core.metrics`) used by
`src.health.endpoints` while keeping instrumentation optional/safe.
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from prometheus_client import Counter, Histogram
except Exception:  # pragma: no cover - optional dependency path
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

_request_count_metric: Optional["Counter"] = None
_request_duration_metric: Optional["Histogram"] = None


def _init_metrics() -> None:
    """Initialize metrics once; remain operational if registration fails."""
    global _request_count_metric, _request_duration_metric

    if Counter is None or Histogram is None:
        return

    if _request_count_metric is None:
        try:
            _request_count_metric = Counter(
                "health_endpoint_requests_total",
                "Total health endpoint requests",
                ["endpoint", "status_code"],
            )
        except Exception:
            logger.debug("Could not initialize health request counter", exc_info=True)

    if _request_duration_metric is None:
        try:
            _request_duration_metric = Histogram(
                "health_endpoint_request_duration_seconds",
                "Health endpoint request duration in seconds",
                ["endpoint"],
            )
        except Exception:
            logger.debug(
                "Could not initialize health request duration histogram", exc_info=True
            )


def record_request_count(endpoint: str, status_code: str) -> None:
    """Record a single request count for a health endpoint."""
    _init_metrics()
    if _request_count_metric is None:
        return

    try:
        _request_count_metric.labels(
            endpoint=str(endpoint), status_code=str(status_code)
        ).inc()
    except Exception:
        logger.debug("Failed to increment health request counter", exc_info=True)


def record_request_duration(endpoint: str, duration_seconds: float) -> None:
    """Record observed request duration for a health endpoint."""
    _init_metrics()
    if _request_duration_metric is None:
        return

    try:
        _request_duration_metric.labels(endpoint=str(endpoint)).observe(
            max(0.0, float(duration_seconds))
        )
    except Exception:
        logger.debug("Failed to observe health request duration", exc_info=True)

