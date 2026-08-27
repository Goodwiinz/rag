"""Regression coverage for authenticated analytics rate-limit context."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.middleware.rate_limiting import AnalyticsRateLimitMiddleware

pytestmark = pytest.mark.unit


def _analytics_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/analytics/quality",
            "raw_path": b"/api/v1/analytics/quality",
            "query_string": b"",
            "headers": [],
            "client": ("10.0.0.9", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    request.state.user_id = "user-42"
    request.state.user_role = "admin"
    return request


@pytest.mark.asyncio
async def test_authenticated_admin_uses_per_user_key_and_role_limit() -> None:
    middleware = AnalyticsRateLimitMiddleware(Mock())
    middleware.rate_limiter = Mock()
    middleware.rate_limiter.is_allowed.return_value = (
        True,
        {
            "current_requests": 0,
            "limit": 2000,
            "window": 3600,
            "reset_time": 0,
            "retry_after": None,
        },
    )
    call_next = AsyncMock(return_value=Response())

    await middleware.dispatch(_analytics_request(), call_next)

    middleware.rate_limiter.is_allowed.assert_called_once_with(
        key="analytics:user-42:api_calls",
        limit=2000,
        window=3600,
    )
