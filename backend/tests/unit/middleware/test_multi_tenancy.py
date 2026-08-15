"""Tests for multi-tenancy middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_dispatch_attaches_db_session_to_request_state():
    """Middleware attaches validated db session to request.state."""
    from starlette.testclient import TestClient

    mock_db = AsyncMock()
    mock_db.is_active = True

    with (
        patch(
            "src.middleware.multi_tenancy.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
        patch(
            "src.middleware.multi_tenancy.MultiTenancyMiddleware._should_skip_tenant_validation",
            return_value=False,
        ),
        patch(
            "src.middleware.multi_tenancy.MultiTenancyMiddleware._extract_tenant_info",
            new_callable=AsyncMock,
            return_value={
                "organization_id": "org-123",
                "user_id": "user-456",
                "role": "user",
            },
        ),
        patch(
            "src.middleware.multi_tenancy.MultiTenancyMiddleware._validate_tenant_access",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.middleware.multi_tenancy.verify_token",
            return_value=MagicMock(user_id="user-456", role="user"),
        ),
    ):
        from fastapi import FastAPI, Request

        from src.middleware.multi_tenancy import MultiTenancyMiddleware

        app = FastAPI()
        app.add_middleware(MultiTenancyMiddleware)

        captured = {}

        @app.get("/test-db-attach")
        async def test_endpoint(request: Request):
            captured["has_db"] = hasattr(request.state, "db")
            captured["db_is_async_mock"] = (
                request.state.db is mock_db if hasattr(request.state, "db") else False
            )
            return {"ok": True}

        client = TestClient(app)
        response = client.get(
            "/test-db-attach", headers={"Authorization": "Bearer fake-token"}
        )
        assert response.status_code == 200
        assert (
            captured.get("has_db") is True
        ), "request.state.db should have been set by middleware"
        assert (
            captured.get("db_is_async_mock") is True
        ), "request.state.db should be the same session"


@pytest.mark.asyncio
async def test_dispatch_skipped_paths_do_not_set_db():
    """Middleware skips tenant validation for paths like /health."""
    with patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._should_skip_tenant_validation",
        return_value=True,
    ):
        from fastapi import FastAPI, Request

        from src.middleware.multi_tenancy import MultiTenancyMiddleware

        app = FastAPI()
        app.add_middleware(MultiTenancyMiddleware)

        captured = {}

        @app.get("/health")
        async def health_endpoint(request: Request):
            captured["has_db"] = hasattr(request.state, "db")
            return {"status": "ok"}

        from starlette.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert (
            captured.get("has_db") is False
        ), "request.state.db should NOT be set for skipped paths"


@pytest.mark.asyncio
async def test_agent_stream_path_sets_tenant_context():
    """Agent routes need tenant context for downstream services."""
    from starlette.testclient import TestClient

    mock_db = AsyncMock()
    mock_db.is_active = True

    with (
        patch(
            "src.middleware.multi_tenancy.AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_db),
                __aexit__=AsyncMock(return_value=False),
            ),
        ),
        patch(
            "src.middleware.multi_tenancy.MultiTenancyMiddleware._extract_tenant_info",
            new_callable=AsyncMock,
            return_value={
                "organization_id": "org-123",
                "user_id": "user-456",
                "role": "user",
            },
        ),
        patch(
            "src.middleware.multi_tenancy.MultiTenancyMiddleware._validate_tenant_access",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        from fastapi import FastAPI

        from src.middleware.multi_tenancy import (
            MultiTenancyMiddleware,
            get_current_tenant_id,
        )

        app = FastAPI()
        app.add_middleware(MultiTenancyMiddleware)

        @app.get("/api/v1/agent/stream/probe")
        async def probe_endpoint():
            return {"tenant_id": get_current_tenant_id()}

        client = TestClient(app)
        response = client.get(
            "/api/v1/agent/stream/probe",
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": "org-123"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        # a sub-path of a skipped route still skips (startswith match)
        "/api/v1/auth/refresh/callback",
        "/health",
        "/health/readiness",
        "/docs",
        "/redoc",
        "/openapi.json",
    ],
)
def test_should_skip_tenant_validation_matches_mounted_paths(path):
    """The skip-list must match the *actual* mounted auth routes.

    Auth router is mounted at ``/api/v1`` + ``/auth`` => ``/api/v1/auth/...``
    (main.py:522, api/auth/auth.py:35). A ``startswith`` check against
    ``/auth/login`` never fires, so every login/register/refresh request
    needlessly opens a DB session and runs JWT verification. Regression
    guard for issue #1003.
    """
    from unittest.mock import MagicMock

    from fastapi import Request

    from src.middleware.multi_tenancy import MultiTenancyMiddleware

    middleware = MultiTenancyMiddleware(app=None)
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = path
    assert (
        middleware._should_skip_tenant_validation(mock_request) is True
    ), f"expected skip for {path!r}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/documents",
        "/api/v1/agent/stream",
        "/api/v1/analytics",
        "/health/detailed",
        "/api/v1/sentry-debug",
        "/",  # root must NOT skip — tenant scope applies
    ],
)
def test_should_skip_tenant_validation_does_not_overmatch(path):
    """Skip-list must not swallow tenant-scoped routes or the bare root."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from src.middleware.multi_tenancy import MultiTenancyMiddleware

    middleware = MultiTenancyMiddleware(app=None)
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = path
    assert (
        middleware._should_skip_tenant_validation(mock_request) is False
    ), f"expected NO skip for {path!r}"


def _fast_path_session(db_user):
    """A mock AsyncSessionLocal() context manager whose execute() resolves to
    db_user (or None)."""
    from unittest.mock import AsyncMock

    class _Res:
        def scalars(self):
            return self

        def first(self):
            return db_user

    prov_db = AsyncMock()
    prov_db.execute = AsyncMock(return_value=_Res())
    prov_db.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=prov_db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_fast_path_validates_db_user_and_uses_db_role():
    """Fast path (org embedded in token) now resolves + validates the live DB
    user; the role comes from the DB, not the token claim."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from fastapi import Request

    from src.middleware.multi_tenancy import MultiTenancyMiddleware
    from src.models.user import UserRole

    middleware = MultiTenancyMiddleware(app=None)
    middleware._should_skip_tenant_validation = lambda _: False

    token_data_mock = MagicMock()
    token_data_mock.user_id = "user-456"
    token_data_mock.organization_id = "org-embedded"
    token_data_mock.role = "admin"  # token CLAIMS admin

    db_user = SimpleNamespace(
        id="user-456", organization_id="org-embedded", role=UserRole.USER
    )

    with (
        patch(
            "src.middleware.multi_tenancy.verify_token", return_value=token_data_mock
        ),
        patch(
            "src.middleware.multi_tenancy.AsyncSessionLocal",
            return_value=_fast_path_session(db_user),
        ),
        patch(
            "src.middleware.multi_tenancy.ensure_user_and_org",
            new=AsyncMock(return_value=None),
        ),
    ):
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "Bearer fake-token"
        result = await middleware._extract_tenant_info(mock_request, db=None)

    assert result is not None
    assert result["organization_id"] == "org-embedded"
    assert result["user_id"] == "user-456"
    assert result["role"] == "user"  # DB role wins over token's "admin"


@pytest.mark.asyncio
async def test_fast_path_denies_inactive_user():
    """Fast path returns no context when the DB user is inactive/deleted (the
    active filter excludes the row, so the lookup resolves to None)."""
    from unittest.mock import AsyncMock

    from fastapi import Request

    from src.middleware.multi_tenancy import MultiTenancyMiddleware

    middleware = MultiTenancyMiddleware(app=None)
    middleware._should_skip_tenant_validation = lambda _: False

    token_data_mock = MagicMock()
    token_data_mock.user_id = "user-456"
    token_data_mock.organization_id = "org-embedded"
    token_data_mock.role = "admin"

    with (
        patch(
            "src.middleware.multi_tenancy.verify_token", return_value=token_data_mock
        ),
        patch(
            "src.middleware.multi_tenancy.AsyncSessionLocal",
            return_value=_fast_path_session(None),
        ),
        patch(
            "src.middleware.multi_tenancy.ensure_user_and_org",
            new=AsyncMock(return_value=None),
        ),
    ):
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "Bearer fake-token"
        result = await middleware._extract_tenant_info(mock_request, db=None)

    assert result is None
