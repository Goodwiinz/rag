"""Security response headers (audit #10).

The full ``APISecurityMiddleware`` in ``api_security.py`` is implemented but was
never registered — so every backend response shipped with NO security headers
(notably no ``X-Content-Type-Options: nosniff`` on document downloads served
with an attacker-influenced ``Content-Type``). That middleware, however, also
performs IP blocking, request-body validation and anomaly heuristics in its
``dispatch``; registering it wholesale would be a large, risky behavioural
change. This middleware does ONE thing — add the standard security headers to
every response — with no request-handling side effects, so it is safe to wire
into the app unconditionally.

Differences from ``APISecurityMiddleware._add_security_headers``:
  * ``script-src``/``style-src`` drop ``'unsafe-inline'``/``'unsafe-eval'`` —
    backend responses are JSON/files, never inline-script HTML.
  * Swagger/ReDoc/OpenAPI paths are exempted from CSP (their UI legitimately
    loads inline scripts + a CDN); they are DEBUG-only anyway.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings

# Interactive API-doc surfaces serve HTML that needs inline scripts and a CDN;
# a strict default-src 'self' CSP would break them. They only exist when DEBUG.
_CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")

# Strict CSP for API/file responses: no inline/eval script, deny framing,
# block plugins, pin base-uri and form-action. img/connect stay permissive so
# JSON error pages embedding data URIs or links don't break.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response. Headers only."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        if not request.url.path.startswith(_CSP_EXEMPT_PREFIXES):
            response.headers.setdefault(
                "Content-Security-Policy", _CONTENT_SECURITY_POLICY
            )

        # HSTS only over real HTTPS in production (never on plain-HTTP dev/probes).
        if settings.ENVIRONMENT == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
