"""Tests for the kubelet-probe Host-header exemption.

Kubelet HTTP probes send ``Host: <pod-IP>``, which is not in the trusted-host
allow-list. Probe paths — including ``/health/readiness`` — must bypass
``TrustedHostMiddleware`` or every probe returns HTTP 400. For readiness a 400
would pull *all* pods out of the load balancer at once (total outage), so this
exemption is safety-critical and is verified in isolation from the full app.

The middleware is driven directly at the ASGI layer so the test is independent
of any TestClient/httpx version differences.
"""

import pytest

from src.core.probes import PROBE_EXEMPT_PATHS, ProbeAwareTrustedHostMiddleware

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", "*.gen-text.app"]
POD_IP_HOST = "10.244.3.17"  # kubelet probe Host: not in the allow-list


def _make_inner():
    """A trivial ASGI app that records whether it was reached and returns 200."""
    state = {"reached": False, "path": None}

    async def inner(scope, receive, send):
        state["reached"] = True
        state["path"] = scope["path"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return inner, state


async def _drive(app, path: str, host: str) -> int:
    """Send one GET request through an ASGI app; return the response status."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [(b"host", host.encode())],
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


@pytest.mark.unit
def test_readiness_path_is_probe_exempt():
    # The readiness probe targets /health/readiness; if it is not exempt the
    # kubelet's pod-IP Host header 400s every probe -> all pods leave the LB.
    assert "/health/readiness" in PROBE_EXEMPT_PATHS
    # Liveness/startup path stays exempt too.
    assert "/health" in PROBE_EXEMPT_PATHS


@pytest.mark.unit
async def test_probe_paths_bypass_host_validation_with_pod_ip_host():
    inner, state = _make_inner()
    mw = ProbeAwareTrustedHostMiddleware(inner, allowed_hosts=ALLOWED_HOSTS)

    # Readiness probe from the kubelet (pod-IP Host) must reach the app -> 200.
    status = await _drive(mw, "/health/readiness", POD_IP_HOST)
    assert status == 200
    assert state["reached"] is True
    assert state["path"] == "/health/readiness"


@pytest.mark.unit
async def test_liveness_health_path_bypasses_host_validation():
    inner, state = _make_inner()
    mw = ProbeAwareTrustedHostMiddleware(inner, allowed_hosts=ALLOWED_HOSTS)

    status = await _drive(mw, "/health", POD_IP_HOST)
    assert status == 200
    assert state["reached"] is True


@pytest.mark.unit
async def test_non_probe_path_rejects_untrusted_host():
    inner, state = _make_inner()
    mw = ProbeAwareTrustedHostMiddleware(inner, allowed_hosts=ALLOWED_HOSTS)

    # Non-probe path with an untrusted Host is rejected before reaching the app.
    status = await _drive(mw, "/api/v1/thing", POD_IP_HOST)
    assert status == 400
    assert state["reached"] is False


@pytest.mark.unit
async def test_non_probe_path_allows_trusted_host():
    inner, state = _make_inner()
    mw = ProbeAwareTrustedHostMiddleware(inner, allowed_hosts=ALLOWED_HOSTS)

    status = await _drive(mw, "/api/v1/thing", "testserver")
    assert status == 200
    assert state["reached"] is True
