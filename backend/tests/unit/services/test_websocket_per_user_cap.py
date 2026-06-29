"""Per-user WebSocket connection cap.

The manager enforced only a GLOBAL ``max_connections``; a single user (or a
leaked token) could open thousands of sockets and starve the global budget for
every other tenant. ``max_connections_per_user`` bounds each ``user_id`` and the
over-limit handshake is closed with ``WS_1013`` (try again later) rather than
silently dropped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import status

from src.services.websocket.websocket_manager import EnhancedConnectionManager

pytestmark = pytest.mark.unit


def _mgr(per_user: int = 2) -> EnhancedConnectionManager:
    mgr = EnhancedConnectionManager()
    mgr.max_connections_per_user = per_user
    return mgr


def _fill_user(mgr: EnhancedConnectionManager, user_id: str, n: int) -> None:
    for i in range(n):
        mgr.user_connections[user_id].add(f"{user_id}-conn-{i}")


def _ws() -> AsyncMock:
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


def test_user_at_capacity_predicate():
    mgr = _mgr(per_user=2)
    assert mgr._user_at_capacity("u1") is False
    _fill_user(mgr, "u1", 2)
    assert mgr._user_at_capacity("u1") is True
    # A different user is unaffected.
    assert mgr._user_at_capacity("u2") is False


@pytest.mark.asyncio
async def test_connect_authenticated_rejects_over_per_user_cap():
    mgr = _mgr(per_user=2)
    _fill_user(mgr, "u1", 2)  # already at cap
    mgr._connect_internal = AsyncMock(return_value="should-not-be-called")
    ws = _ws()

    result = await mgr.connect_authenticated(ws, user_id="u1", organization_id="org")

    assert result is None  # rejected
    mgr._connect_internal.assert_not_awaited()  # never registered
    ws.close.assert_awaited_once()
    assert ws.close.await_args.kwargs["code"] == status.WS_1013_TRY_AGAIN_LATER


@pytest.mark.asyncio
async def test_connect_authenticated_allows_under_per_user_cap():
    mgr = _mgr(per_user=2)
    _fill_user(mgr, "u1", 1)  # one below cap
    mgr._connect_internal = AsyncMock(return_value="cid-1")
    ws = _ws()

    result = await mgr.connect_authenticated(ws, user_id="u1", organization_id="org")

    assert result == "cid-1"
    mgr._connect_internal.assert_awaited_once()
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_per_user_cap_is_isolated_between_users():
    mgr = _mgr(per_user=2)
    _fill_user(mgr, "u1", 2)  # u1 maxed
    mgr._connect_internal = AsyncMock(return_value="cid-u2")
    ws = _ws()

    # u2 has zero connections → must be allowed even while u1 is maxed.
    result = await mgr.connect_authenticated(ws, user_id="u2", organization_id="org")

    assert result == "cid-u2"
    mgr._connect_internal.assert_awaited_once()
