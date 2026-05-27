"""Tests for multi-tenancy middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_dispatch_attaches_db_session_to_request_state():
    """Middleware attaches validated db session to request.state."""
    from starlette.testclient import TestClient

    mock_db = AsyncMock()
    mock_db.is_active = True

    with patch(
        "src.middleware.multi_tenancy.AsyncSessionLocal",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_db),
            __aexit__=AsyncMock(return_value=False),
        ),
    ), patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._should_skip_tenant_validation",
        return_value=False,
    ), patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._extract_tenant_info",
        new_callable=AsyncMock,
        return_value={
            "organization_id": "org-123",
            "user_id": "user-456",
            "role": "user",
        },
    ), patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._validate_tenant_access",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "src.middleware.multi_tenancy.verify_token",
        return_value=MagicMock(user_id="user-456", role="user"),
    ):
        from fastapi import FastAPI, Request
        from src.middleware.multi_tenancy import MultiTenancyMiddleware

        app = FastAPI()
        app.add_middleware(MultiTenancyMiddleware)

        captured = {}

        @app.get("/test-db-attach")
        async def test_endpoint(request: Request):
            captured["has_db"] = hasattr(request.state, "db")
            captured["db_is_async_mock"] = request.state.db is mock_db if hasattr(request.state, "db") else False
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test-db-attach", headers={"Authorization": "Bearer fake-token"})
        assert response.status_code == 200
        assert captured.get("has_db") is True, "request.state.db should have been set by middleware"
        assert captured.get("db_is_async_mock") is True, "request.state.db should be the same session"


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
        assert captured.get("has_db") is False, "request.state.db should NOT be set for skipped paths"


@pytest.mark.asyncio
async def test_agent_stream_path_sets_tenant_context():
    """Agent routes need tenant context for downstream services."""
    from starlette.testclient import TestClient

    mock_db = AsyncMock()
    mock_db.is_active = True

    with patch(
        "src.middleware.multi_tenancy.AsyncSessionLocal",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_db),
            __aexit__=AsyncMock(return_value=False),
        ),
    ), patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._extract_tenant_info",
        new_callable=AsyncMock,
        return_value={
            "organization_id": "org-123",
            "user_id": "user-456",
            "role": "user",
        },
    ), patch(
        "src.middleware.multi_tenancy.MultiTenancyMiddleware._validate_tenant_access",
        new_callable=AsyncMock,
        return_value=True,
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


@pytest.mark.asyncio
async def test_fast_path_skips_db_when_org_id_in_token():
    """When token_data already has organization_id, skip the DB lookup."""
    from src.middleware.multi_tenancy import MultiTenancyMiddleware

    middleware = MultiTenancyMiddleware(app=None)
    middleware._should_skip_tenant_validation = lambda _: False

    token_data_mock = MagicMock()
    token_data_mock.user_id = "user-456"
    token_data_mock.organization_id = "org-embedded"
    token_data_mock.role = "user"

    with patch(
        "src.middleware.multi_tenancy.verify_token", return_value=token_data_mock
    ):
        from fastapi import Request
        from unittest.mock import AsyncMock

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "Bearer fake-token"

        result = await middleware._extract_tenant_info(mock_request, db=None)

    assert result is not None
    assert result["organization_id"] == "org-embedded"
    assert result["user_id"] == "user-456"
    assert result["role"] == "user"
