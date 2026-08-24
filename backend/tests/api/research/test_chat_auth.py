"""Auth coverage for /api/v1/chat/health and /api/v1/chat/models (audit B3)."""

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.research import chat as chat_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")
    return app


def test_health_and_models_require_auth() -> None:
    """Unauthenticated requests must be rejected on both endpoints."""
    app = _build_app()

    with TestClient(app) as client:
        assert client.get("/api/v1/chat/health").status_code in (401, 403)
        assert client.get("/api/v1/chat/models").status_code in (401, 403)


def test_health_and_models_accessible_when_authenticated() -> None:
    """With a valid auth override, both endpoints still return 200."""
    app = _build_app()

    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.organization_id = "test-org-id"
    app.dependency_overrides[chat_module.get_current_user] = lambda: mock_user

    try:
        with TestClient(app) as client:
            health_response = client.get("/api/v1/chat/health")
            models_response = client.get("/api/v1/chat/models")

        assert health_response.status_code == 200
        assert "status" in health_response.json()

        assert models_response.status_code == 200
        assert "models" in models_response.json()
    finally:
        app.dependency_overrides.clear()
