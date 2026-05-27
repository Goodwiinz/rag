"""Sentry verification endpoint.

Mirrors the frontend `/sentry-example-page` flow on the backend. Hitting
`GET /api/v1/sentry-debug` raises a deliberate exception so we can confirm
the Sentry SDK forwards events. Disabled in production unless explicitly
opted-in via `SENTRY_DEBUG_ENABLED=true`.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/sentry-debug", tags=["diagnostics"])


class SentryDebugError(RuntimeError):
    """Deliberate exception raised by the verify endpoint."""


def _enabled() -> bool:
    if os.getenv("SENTRY_DEBUG_ENABLED", "").lower() in {"1", "true", "yes"}:
        return True
    env = (os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "").lower()
    return env not in {"prod", "production"}


@router.get("", summary="Trigger a Sentry test event")
def trigger_sentry_event() -> None:
    """Raises an exception so Sentry can capture it.

    Returns 404 in production unless `SENTRY_DEBUG_ENABLED=true`.
    """
    if not _enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    raise SentryDebugError(
        "This error is raised on the backend to verify the Sentry integration."
    )
