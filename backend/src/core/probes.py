"""Kubelet probe helpers.

Kubelet HTTP probes send ``Host: <pod-IP>``, which is not in the trusted-host
allow-list. Without an exemption, ``TrustedHostMiddleware`` answers those probe
requests with HTTP 400, the probe fails, and the pod crash-loops (liveness) or
is pulled from the Service load balancer (readiness).

``PROBE_EXEMPT_PATHS`` is the single source of truth for the paths the kubelet
actually hits. It is kept in a dependency-light module (only Starlette) so the
list — and the exemption behaviour — can be unit-tested without importing the
whole application.

SAFETY: every path used by a Kubernetes probe MUST appear here. In particular
``/health/readiness`` is targeted by the backend readiness probe; if it is
missing, every readiness probe returns 400 and *all* pods leave the load
balancer at once → total outage.
"""

from __future__ import annotations

from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Paths hit by kubelet HTTP probes (and Prometheus scraping) that must bypass
# Host-header validation. Keep in sync with the probe paths configured in the
# Helm chart (infrastructure/helm/.../values-*.yaml backend.healthCheck.*).
PROBE_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",  # liveness + startup probe (process-alive)
        "/health/readiness",  # readiness probe (dependency-aware)
        "/healthz",
        "/readyz",
        "/livez",
        "/metrics",  # Prometheus scrape
    }
)


class ProbeAwareTrustedHostMiddleware(TrustedHostMiddleware):
    """``TrustedHostMiddleware`` that skips host validation for probe paths.

    Kubelet probes cannot set a trusted Host header, so requests to the paths
    in :data:`PROBE_EXEMPT_PATHS` are passed straight through to the app; all
    other requests go through the normal trusted-host check.
    """

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        if scope.get("type") == "http" and scope.get("path") in PROBE_EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
