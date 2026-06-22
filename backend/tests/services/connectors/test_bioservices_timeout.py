"""Regression: BioServices lookups are time-bounded.

search() ran the blocking bioservices call via asyncio.to_thread with NO
timeout, so a hung upstream pinned a worker in the shared executor and could
exhaust the pool (stalling every other to_thread caller). search() now wraps
the call in asyncio.wait_for and returns [] on timeout.
"""

import time

import pytest

from src.services.connectors import bioservices_bridge as bb


@pytest.mark.asyncio
async def test_search_returns_empty_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bb, "_bioservices_available", lambda: True)
    monkeypatch.setattr(bb, "_BIOSERVICES_TIMEOUT_SECONDS", 0.05)

    conn = bb.BioServicesBridgeConnector()

    def _slow(*_args: object, **_kwargs: object) -> list:
        time.sleep(0.5)  # blocks past the 0.05s bound
        return ["should-not-arrive"]

    monkeypatch.setattr(conn, "_sync_search", _slow)

    results = await conn.search("braf", filters={"service": "kegg"})
    assert results == []


@pytest.mark.asyncio
async def test_search_returns_results_within_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bb, "_bioservices_available", lambda: True)
    monkeypatch.setattr(bb, "_BIOSERVICES_TIMEOUT_SECONDS", 5.0)

    conn = bb.BioServicesBridgeConnector()
    sentinel = ["ok"]
    monkeypatch.setattr(conn, "_sync_search", lambda *a, **k: sentinel)

    results = await conn.search("braf", filters={"service": "kegg"})
    assert results == sentinel
