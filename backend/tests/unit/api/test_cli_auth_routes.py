from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client() -> TestClient:
    from src.api.auth.cli_auth import get_cli_auth_session_store
    from src.api.auth.cli_auth import router as cli_auth_router
    from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore

    app = FastAPI()
    app.include_router(cli_auth_router, prefix="/api/v1")
    store = InMemoryCLIAuthSessionStore()
    app.dependency_overrides[get_cli_auth_session_store] = lambda: store

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_cli_auth_start_returns_session_and_browser_url(client: TestClient) -> None:
    response = client.post("/api/v1/cli-auth/start")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["verification_code"]
    assert "/cli-auth?" in body["browser_url"]
    assert body["poll_token"]
    assert body["poll_interval_seconds"] == 2


def test_cli_auth_status_returns_pending_session(client: TestClient) -> None:
    started = client.post("/api/v1/cli-auth/start").json()

    response = client.get(
        f"/api/v1/cli-auth/status/{started['session_id']}",
        params={"poll_token": started["poll_token"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["session_id"] == started["session_id"]
