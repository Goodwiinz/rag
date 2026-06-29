"""Regression: Alpha Vantage must not log its API key on an HTTP error.

The apikey is sent as a URL query param. httpx's `raise_for_status()` raises an
HTTPStatusError whose str() embeds the full request URL (including the key). The
generic `except Exception: logger.error(error=str(exc))` would log that key. A
dedicated `except httpx.HTTPStatusError` now logs only the status code + query.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import src.services.connectors.alpha_vantage as av
from src.services.connectors.alpha_vantage import AlphaVantageConnector

SECRET = "SUPERSECRETKEY123"


def _client_raising_http_status_error():
    """An AsyncClient() context manager whose get().raise_for_status() raises an
    HTTPStatusError whose message carries the apikey (as the real URL would)."""
    exc = httpx.HTTPStatusError(
        f"Client error '401' for url "
        f"'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&apikey={SECRET}'",
        request=MagicMock(),
        response=MagicMock(status_code=401),
    )
    resp = MagicMock()
    resp.raise_for_status = MagicMock(side_effect=exc)

    inner = MagicMock()
    inner.get = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.unit
@pytest.mark.parametrize("method,arg", [("search", "AAPL"), ("fetch_by_id", "AAPL")])
def test_http_error_never_logs_apikey(monkeypatch, method, arg):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", SECRET)

    calls = []
    fake_logger = MagicMock()
    fake_logger.warning.side_effect = lambda *a, **k: calls.append((a, k))
    fake_logger.error.side_effect = lambda *a, **k: calls.append((a, k))

    with (
        patch.object(av, "logger", fake_logger),
        patch.object(
            av.httpx, "AsyncClient", return_value=_client_raising_http_status_error()
        ),
    ):
        out = asyncio.run(getattr(AlphaVantageConnector(), method)(arg))

    # Graceful empty result, and the key never appears in any log call.
    assert out in ([], None)
    assert SECRET not in repr(calls), f"apikey leaked into logs: {calls}"
    # The HTTP-specific handler (status, no str(exc)) fired, not the generic one.
    fake_logger.warning.assert_called()
    fake_logger.error.assert_not_called()
