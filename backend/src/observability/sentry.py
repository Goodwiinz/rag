"""Sentry SDK initialization for the FastAPI backend.

Mirrors the frontend pattern: gated on `SENTRY_DSN`, no-op when unset, sample
rates and environment driven by env vars. Must be called before the FastAPI
app is constructed so the SDK can patch frameworks early.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

logger = logging.getLogger(__name__)

_initialized = False


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, falling back to %s", name, raw, default)
        return default


def _scrub_sensitive(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Strip auth headers/cookies before send. send_default_pii=False already
    drops most PII; this guarantees we never leak bearer tokens.
    """
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for key in list(headers.keys()):
        if key.lower() in {"authorization", "cookie", "x-api-key", "proxy-authorization"}:
            headers[key] = "[Filtered]"
    if "cookies" in request:
        request["cookies"] = "[Filtered]"
    return event


def init_sentry() -> bool:
    """Initialize the Sentry SDK. Returns True if active, False if disabled.

    Reads:
      - SENTRY_DSN              (required; absent => no-op)
      - SENTRY_ENVIRONMENT      (defaults to ENVIRONMENT, then "development")
      - SENTRY_TRACES_SAMPLE_RATE  (default 0.1 in prod, 1.0 elsewhere)
      - SENTRY_PROFILES_SAMPLE_RATE (default 0.0)
      - APP_VERSION             (release tag; defaults to "unknown")
    """
    global _initialized
    if _initialized:
        return True

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry DSN not set — error tracking disabled")
        return False

    environment = (
        os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "development"
    )
    is_prod = environment.lower() in {"prod", "production"}
    traces_sample_rate = _float_env(
        "SENTRY_TRACES_SAMPLE_RATE", 0.1 if is_prod else 1.0
    )
    profiles_sample_rate = _float_env("SENTRY_PROFILES_SAMPLE_RATE", 0.0)
    release = os.getenv("APP_VERSION") or os.getenv("GIT_SHA") or "unknown"

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=False,
        attach_stacktrace=True,
        before_send=_scrub_sensitive,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            AsyncioIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    sentry_sdk.set_tag("service", "nous-backend")

    _initialized = True
    logger.info(
        "Sentry initialized (env=%s, traces=%s, profiles=%s, release=%s)",
        environment,
        traces_sample_rate,
        profiles_sample_rate,
        release,
    )
    return True
