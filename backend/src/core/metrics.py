"""
Backward-compatible metrics helpers used by legacy health endpoints.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

_counts_lock = Lock()
_durations_lock = Lock()
_request_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
_request_durations: defaultdict[str, list[float]] = defaultdict(list)


def record_request_count(endpoint: str, status_code: str) -> None:
    """
    Record a request count for an endpoint/status code pair.

    This keeps lightweight in-process counters so legacy imports continue to work
    even when the full observability stack is unavailable.
    """

    key = (endpoint, str(status_code))
    with _counts_lock:
        _request_counts[key] += 1


def record_request_duration(endpoint: str, duration_seconds: float) -> None:
    """
    Record request duration for an endpoint.

    Durations are stored in memory for compatibility with older callers.
    """

    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError):
        logger.debug("Ignoring non-numeric request duration for endpoint=%s", endpoint)
        return

    with _durations_lock:
        _request_durations[endpoint].append(duration)
