"""
Metrics stub module for health endpoints.
"""


def record_request_count(endpoint: str, method: str, status: int) -> None:
    """Record request count metric (stub)."""
    pass


def record_request_duration(endpoint: str, method: str, duration: float) -> None:
    """Record request duration metric (stub)."""
    pass
