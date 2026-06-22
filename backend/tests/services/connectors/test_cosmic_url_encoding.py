"""Regression: COSMIC connector URL-encodes the user-supplied gene query.

The gene symbol was interpolated raw into the request path
(f"{_API_BASE_URL}/genes/{query}"), so a query containing "../", "?", "&" or
"#" could inject extra path segments / query params into the COSMIC request
that carries the Basic-auth header. The query is now percent-encoded, and
follow_redirects is disabled so the credentials cannot be replayed to a
redirect target.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.connectors.cosmic import COSMICConnector


def _mock_client() -> AsyncMock:
    response = MagicMock()
    response.json.return_value = []
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_search_percent_encodes_query_in_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMIC_AUTH", "user:pass")
    client = _mock_client()

    with patch(
        "src.services.connectors.cosmic.httpx.AsyncClient", return_value=client
    ) as async_client:
        await COSMICConnector().search("../../admin?x=1", max_results=5)

    called_url = client.get.call_args.args[0]
    # No raw path-traversal / query-injection characters survive.
    assert "../" not in called_url
    assert "?x=1" not in called_url
    assert "genes/..%2F..%2Fadmin%3Fx%3D1" in called_url
    # Credentials must not follow a redirect off-host.
    kwargs: Dict[str, Any] = async_client.call_args.kwargs
    assert kwargs.get("follow_redirects") is False


@pytest.mark.asyncio
async def test_unauthenticated_fallback_url_encodes_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COSMIC_AUTH", raising=False)

    results = await COSMICConnector().search("a b&c", max_results=5)

    # Offline fallback still must not emit a raw, ambiguous URL.
    assert results
    assert "a b&c" not in results[0].url
    assert "ln=a%20b%26c" in results[0].url
