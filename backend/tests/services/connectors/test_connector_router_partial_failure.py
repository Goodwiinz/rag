"""Regression: a failing connector is surfaced, not silently swallowed.

The /connectors/search endpoint ran every connector with
asyncio.gather(return_exceptions=True) and `continue`d past any that raised
with no log and no signal — a failed connector (auth/upstream error) was
indistinguishable from "searched and found nothing". The endpoint now logs each
failure and returns the failed connector names in `failed_connectors`.
"""

from typing import Any, Dict, List, Optional

import pytest

from src.api.connectors.router import SearchRequest, search_connectors
from src.services.connectors import connector_registry
from src.services.connectors.base import (
    ConnectorCapability,
    ConnectorDomain,
    ConnectorInfo,
    ConnectorResult,
    ExternalDBConnector,
)


def _info(name: str) -> ConnectorInfo:
    return ConnectorInfo(
        name=name,
        display_name=name,
        description="test",
        domains=[ConnectorDomain.GENERAL],
        capabilities=[ConnectorCapability.SEARCH],
        base_url="https://example.com",
    )


class _GoodConn(ExternalDBConnector):
    @property
    def info(self) -> ConnectorInfo:
        return _info("good_conn")

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        del filters, max_results
        return [
            ConnectorResult(
                id="g-1", title=query, source="good_conn", url="https://example.com"
            )
        ]


class _BadConn(ExternalDBConnector):
    @property
    def info(self) -> ConnectorInfo:
        return _info("bad_conn")

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ConnectorResult]:
        raise RuntimeError("upstream 503")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_connector_reported_not_swallowed() -> None:
    connector_registry.register(_GoodConn())
    connector_registry.register(_BadConn())
    try:
        resp = await search_connectors(
            SearchRequest(query="hello", connectors=["good_conn", "bad_conn"])
        )
    finally:
        connector_registry._connectors.pop("good_conn", None)
        connector_registry._connectors.pop("bad_conn", None)

    # The failure is visible, not hidden as an empty result set.
    assert "bad_conn" in resp.failed_connectors
    assert "good_conn" not in resp.failed_connectors
    # Both were attempted; only the good one contributed results.
    assert {"good_conn", "bad_conn"} <= set(resp.connectors_searched)
    assert resp.total_results == 1
    assert all(r.source != "bad_conn" for r in resp.results)
