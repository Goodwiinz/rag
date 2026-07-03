"""Tests for wiring the app's own exception hierarchies to structured handlers.

Daily code-quality audit (PR #955, backend/src/exceptions):

  * Finding #1 (High): ``setup_error_handlers()`` was never called, so
    ``main.py`` had no handler for ``RAGException`` / ``AnalyticsException`` /
    ``SQLAlchemyError``. A raised analytics ``PermissionDeniedException`` (which
    should be 403) or ``RateLimitExceededException`` (429) fell through to the
    generic ``Exception`` handler and returned a generic **500**. The fix
    registers those three handlers in ``main.py``.
  * Finding #2 (Medium): ``ConfigurationException`` was defined twice — a dead
    ``RAGException`` subclass in ``src/exceptions/__init__.py`` and the live
    ``AnalyticsException`` subclass. The dead one was removed to kill the
    name collision.

These tests build a FastAPI app that mirrors main.py's wiring (a generic
``Exception`` catch-all PLUS the three specific handlers) and assert the
specific handlers win via Starlette's MRO lookup, with correct status codes
and structured bodies.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import src.exceptions as exc_pkg
from src.exceptions import ValidationException
from src.exceptions.analytics_exceptions import (
    AnalyticsException,
    ConfigurationException,
    PermissionDeniedException,
    RateLimitExceededException,
)
from src.exceptions.error_handlers import (
    analytics_exception_handler,
    database_exception_handler,
    rag_exception_handler,
)
from src.exceptions import RAGException


def _build_app() -> FastAPI:
    app = FastAPI()

    # Mirror main.py's generic catch-all (the one that used to swallow every
    # RAGException/AnalyticsException as a 500).
    async def _generic(request, exc):  # noqa: ANN001
        return JSONResponse(
            status_code=500, content={"error": {"type": "internal_error"}}
        )

    app.add_exception_handler(Exception, _generic)

    # The fix under test: the same three registrations added to main.py.
    app.add_exception_handler(RAGException, rag_exception_handler)
    app.add_exception_handler(AnalyticsException, analytics_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)

    @app.get("/rag")
    async def _rag():
        raise ValidationException("bad input")  # RAGException subclass, 400

    @app.get("/perm")
    async def _perm():
        raise PermissionDeniedException(
            required_permission="analytics:read", user_role="guest"
        )

    @app.get("/rate")
    async def _rate():
        raise RateLimitExceededException(limit=100, window=60, retry_after=30)

    @app.get("/config")
    async def _config():
        raise ConfigurationException(
            config_key="retention_days", config_value="-1", reason="must be positive"
        )

    @app.get("/db")
    async def _db():
        raise SQLAlchemyError("connection failed while running SELECT secret_col")

    @app.get("/boom")
    async def _boom():
        raise ValueError("something unrelated")

    return app


@pytest.fixture
def client() -> TestClient:
    # raise_server_exceptions=False so the generic Exception path returns its
    # 500 response instead of re-raising through ServerErrorMiddleware.
    return TestClient(_build_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Finding #1 — the previously-unwired handlers now produce correct responses
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rag_exception_uses_subclass_status_and_structured_body(client):
    resp = client.get("/rag")
    assert resp.status_code == 400  # ValidationException.status_code, not 500
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "bad input"


@pytest.mark.unit
def test_permission_denied_returns_403_not_generic_500(client):
    """The core bug: this used to hit the generic handler and 500."""
    resp = client.get("/perm")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "PERMISSION_DENIED"
    # analytics handler surfaces the user-friendly message
    assert "permission" in body["error"]["message"].lower()


@pytest.mark.unit
def test_rate_limit_returns_429_with_retry_after_header(client):
    resp = client.get("/rate")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.unit
def test_analytics_configuration_exception_returns_structured_500(client):
    """The exact type raised 12x in RBAC/tenant services — now structured."""
    resp = client.get("/config")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "CONFIGURATION_ERROR"
    # It is NOT the generic fallthrough shape.
    assert body["error"].get("type") != "internal_error"


@pytest.mark.unit
def test_sqlalchemy_error_returns_sanitized_500_without_leaking_sql(client):
    resp = client.get("/db")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "DATABASE_ERROR"
    # The raw SQL / internal detail must not leak into the response.
    assert "SELECT secret_col" not in resp.text


@pytest.mark.unit
def test_unrelated_exception_still_hits_generic_handler(client):
    """MRO precedence works both ways: registering specific handlers must not
    steal unrelated exceptions from the generic catch-all."""
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.json()["error"]["type"] == "internal_error"


# ---------------------------------------------------------------------------
# Finding #2 — the duplicate ConfigurationException collision is gone
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configuration_exception_collision_removed():
    # The dead RAGException-subclass duplicate (and its child) are gone...
    assert not hasattr(exc_pkg, "ConfigurationException")
    assert not hasattr(exc_pkg, "MissingConfigException")
    # ...while the live analytics one remains the single source of truth.
    from src.exceptions.analytics_exceptions import (
        ConfigurationException as AnalyticsConfig,
    )

    assert issubclass(AnalyticsConfig, AnalyticsException)
