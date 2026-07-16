"""AU4: a WebSocket's JWT was verified once at connect and never re-checked.

A revoked/expired session kept receiving its own org's realtime pushes until
the socket happened to drop for an unrelated reason (client close, network
blip, ...). ``ConnectionInfo.expires_at`` now carries the authenticated
token's own ``exp`` (stamped at connect time in websocket_v2.py from the
``TokenData`` returned by ``verify_token``), and the periodic heartbeat
monitor closes any connection whose token has expired (close code 4002,
mirroring the connect-time "token expired" rejection code).

``TokenData.exp`` is built via ``datetime.utcfromtimestamp`` — naive UTC (see
security.py) — and the codebase's other exp comparison
(``token_data.exp < datetime.utcnow()``) is naive-vs-naive. The heartbeat
monitor mirrors that: it must NOT compare against the timezone-aware
``current_time`` it already uses for the missing-heartbeat check, or every
live connection would appear "expired" (aware > naive raises TypeError, but
if compared the wrong direction after a tz-normalizing fix it could instead
silently close everything) — hence the explicit not-yet-expired case below.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.services.websocket.websocket_manager import (
    ConnectionInfo,
    EnhancedConnectionManager,
)

pytestmark = pytest.mark.unit


def _ws() -> AsyncMock:
    ws = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _conn(connection_id: str, ws: AsyncMock, expires_at=None) -> ConnectionInfo:
    now = datetime.now(timezone.utc)
    return ConnectionInfo(
        user_id="u-1",
        organization_id="org-1",
        connection_id=connection_id,
        websocket=ws,
        connected_at=now,
        last_heartbeat=now,  # fresh — must not trip the missing-heartbeat path
        subscribed_channels=set(),
        expires_at=expires_at,
    )


def _mgr() -> EnhancedConnectionManager:
    mgr = EnhancedConnectionManager()
    mgr._log_connection_event = AsyncMock()
    return mgr


async def _run_one_heartbeat_tick(mgr: EnhancedConnectionManager) -> None:
    """Run exactly one iteration of the otherwise-infinite heartbeat loop."""
    calls = {"n": 0}

    async def fake_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError()

    with patch("src.services.websocket.websocket_manager.asyncio.sleep", fake_sleep):
        await mgr._heartbeat_monitor()


@pytest.mark.asyncio
async def test_expired_connection_is_closed_with_4002():
    mgr = _mgr()
    ws = _ws()
    past = datetime.utcnow() - timedelta(minutes=5)
    conn = _conn("c-expired", ws, expires_at=past)
    mgr.active_connections[conn.connection_id] = conn
    mgr.user_connections[conn.user_id].add(conn.connection_id)
    mgr.organization_connections[conn.organization_id].add(conn.connection_id)

    await _run_one_heartbeat_tick(mgr)

    ws.close.assert_awaited_once()
    assert ws.close.await_args.kwargs["code"] == 4002
    assert conn.connection_id not in mgr.active_connections


@pytest.mark.asyncio
async def test_not_yet_expired_connection_is_not_closed():
    """Guards against a tz-comparison regression that would close every live
    connection on the very first heartbeat tick."""
    mgr = _mgr()
    ws = _ws()
    future = datetime.utcnow() + timedelta(hours=1)
    conn = _conn("c-live", ws, expires_at=future)
    mgr.active_connections[conn.connection_id] = conn

    await _run_one_heartbeat_tick(mgr)

    ws.close.assert_not_awaited()
    assert conn.connection_id in mgr.active_connections


@pytest.mark.asyncio
async def test_connection_without_expiry_is_not_closed():
    """Back-compat: connections that never got a token expiry stamped (e.g.
    the legacy connect() path) are not touched by this rule."""
    mgr = _mgr()
    ws = _ws()
    conn = _conn("c-no-exp", ws, expires_at=None)
    mgr.active_connections[conn.connection_id] = conn

    await _run_one_heartbeat_tick(mgr)

    ws.close.assert_not_awaited()
    assert conn.connection_id in mgr.active_connections
