"""
Verifies TrustedHostMiddleware is active during tests (not bypassed by DEBUG=true).

FastAPI's TestClient sends Host: testserver by default. That host must be in the
allowed_hosts list so normal test requests succeed, while truly unknown hosts are
still rejected with 400.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_trusted_host_allows_testclient_host(test_app):
    """TestClient's default host 'testserver' must be in the allowlist."""
    with TestClient(test_app, raise_server_exceptions=False) as client:
        resp = client.get("/health")
    assert resp.status_code != 400, (
        "TrustedHostMiddleware rejected 'testserver' — add it to allowed_hosts in main.py"
    )


@pytest.mark.unit
def test_trusted_host_rejects_unknown_host(test_app):
    """TrustedHostMiddleware must reject hosts not in the allowlist."""
    with TestClient(test_app, raise_server_exceptions=False) as client:
        resp = client.get("/health", headers={"Host": "evil.attacker.com"})
    assert resp.status_code == 400, (
        "TrustedHostMiddleware did not reject an unknown host — middleware may be bypassed"
    )
