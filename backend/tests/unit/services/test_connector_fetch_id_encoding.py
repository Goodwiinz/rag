"""A record_id is user input from the URL path and must be encoded.

`GET /connectors/{connector_name}/{record_id}` passes `record_id` straight to
the connector's `fetch_by_id`, and four connectors interpolated it **raw** into
a request URL path::

    zinc:    f"{_BASE_URL}/substances/{record_id}.json"
    uniprot: f"{_FETCH_URL}/{record_id}.json"
    pubchem: f"{_COMPOUND_URL}/cid/{record_id}/JSON"
    chembl:  f"{_BASE_URL}/molecule/{record_id}.json"

pubchem already did the right thing in its *search* path
(`quote(query, safe="")`) but not here — the convention existed and these paths
skipped it. An id containing a space, `#`, `?` or `%` produced a malformed
request or a silent 404 for a legitimate record, and `?`/`#` injected a query
or fragment into the request to the upstream API.

The host and scheme are fixed constants, so this is a correctness and
consistency fix rather than an SSRF: encoding with `safe=""` keeps the value
inside its single path segment.
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# A record_id exercising the characters that break raw interpolation:
# path separator, query, fragment, percent, space, plus.
_HOSTILE_ID = "ab/../x?q=1#f %20+z"


def _capturing_client(calls: List[str]) -> MagicMock:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    async def _get(url: str, *a: Any, **kw: Any) -> MagicMock:
        calls.append(url)
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock()
        return resp

    client.get = AsyncMock(side_effect=_get)
    return client


@pytest.mark.parametrize(
    "module_path, factory",
    [
        ("src.services.connectors.zinc", "ZINCConnector"),
        ("src.services.connectors.uniprot", "UniProtConnector"),
        ("src.services.connectors.pubchem", "PubChemConnector"),
        ("src.services.connectors.chembl", "ChEMBLConnector"),
    ],
)
async def test_record_id_is_percent_encoded_into_one_path_segment(
    module_path: str, factory: str
) -> None:
    import importlib

    module = importlib.import_module(module_path)
    connector_cls = getattr(module, factory)

    calls: List[str] = []
    with patch.object(
        module.httpx, "AsyncClient", return_value=_capturing_client(calls)
    ):
        await connector_cls().fetch_by_id(_HOSTILE_ID)

    assert calls, f"{factory} never issued a request"
    url = calls[-1]

    # The raw id would have introduced a query, a fragment, and extra path
    # separators. Encoded, none of those characters reach the URL structure.
    path_and_after = url.split("://", 1)[-1].split("/", 1)[-1]
    assert "?" not in path_and_after, f"{factory}: id opened a query string: {url}"
    assert "#" not in path_and_after, f"{factory}: id opened a fragment: {url}"
    assert " " not in url, f"{factory}: unencoded space reached the URL: {url}"
    # The literal traversal segment must not survive as its own path segment.
    assert "/../" not in url, f"{factory}: id introduced a path segment: {url}"
    # It should appear percent-encoded instead.
    assert (
        "%2F" in url or "%2f" in url
    ), f"{factory}: the path separator in the id was not encoded: {url}"
