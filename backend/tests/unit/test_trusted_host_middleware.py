"""
Verifies that TrustedHostMiddleware correctly allows and rejects hosts.

Uses a minimal standalone app to test the middleware in isolation,
independent of settings.DEBUG which gates it in the production app.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.trustedhost import TrustedHostMiddleware


ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "*.gen-text.app"]


@pytest.fixture
def trusted_host_app():
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


@pytest.mark.unit
def test_trusted_host_allows_testclient_host(trusted_host_app):
    """TestClient's default host 'testserver' must be in the allowlist."""
    with TestClient(trusted_host_app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200, (
        f"TrustedHostMiddleware rejected 'testserver' — check ALLOWED_HOSTS. Got: {resp.status_code}"
    )


@pytest.mark.unit
def test_trusted_host_rejects_unknown_host(trusted_host_app):
    """TrustedHostMiddleware must reject hosts not in the allowlist."""
    with TestClient(trusted_host_app, raise_server_exceptions=False) as client:
        resp = client.get("/health", headers={"Host": "evil.attacker.com"})
    assert resp.status_code == 400, (
        f"TrustedHostMiddleware did not reject an unknown host. Got: {resp.status_code}"
    )
