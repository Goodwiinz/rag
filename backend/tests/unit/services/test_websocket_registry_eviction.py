"""R4-L16: EnhancedConnectionManager's defaultdict(set) registries must not
retain empty entries forever. user_connections / organization_connections /
channel_subscribers never dropped a key on disconnect/unsubscribe, so a
user, org, or channel with zero live connections still sat in memory.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.websocket.websocket_manager import (
    ConnectionInfo,
    EnhancedConnectionManager,
)

pytestmark = pytest.mark.unit


class FakeWS:
    async def send_json(self, payload):
        pass

    async def close(self, *args, **kwargs):
        pass


def _now():
    return datetime.now(timezone.utc)


def _register(mgr, *, user_id, org_id, channels=(), conn_id=None):
    ws = FakeWS()
    cid = conn_id or f"c-{user_id}-{org_id}"
    conn = ConnectionInfo(
        user_id=user_id,
        organization_id=org_id,
        connection_id=cid,
        websocket=ws,
        connected_at=_now(),
        last_heartbeat=_now(),
        subscribed_channels=set(channels),
        client_info={"role": "USER"},
    )
    mgr.active_connections[cid] = conn
    mgr.user_connections[user_id].add(cid)
    mgr.organization_connections[org_id].add(cid)
    for ch in channels:
        mgr.channel_subscribers[ch].add(cid)
    return conn, ws


@pytest.mark.asyncio
async def test_disconnect_evicts_empty_registry_entries():
    mgr = EnhancedConnectionManager()
    _register(mgr, user_id="u1", org_id="orgA", channels=["ch1"], conn_id="c1")

    assert "u1" in mgr.user_connections
    assert "orgA" in mgr.organization_connections
    assert "ch1" in mgr.channel_subscribers

    await mgr.disconnect("c1")

    assert "u1" not in mgr.user_connections
    assert "orgA" not in mgr.organization_connections
    assert "ch1" not in mgr.channel_subscribers


@pytest.mark.asyncio
async def test_disconnect_keeps_registry_entries_with_other_live_connections():
    mgr = EnhancedConnectionManager()
    _register(mgr, user_id="u1", org_id="orgA", channels=["ch1"], conn_id="c1")
    _register(mgr, user_id="u1", org_id="orgA", channels=["ch1"], conn_id="c2")

    await mgr.disconnect("c1")

    # c2 is still live under the same user/org/channel -> must not be evicted.
    assert mgr.user_connections["u1"] == {"c2"}
    assert mgr.organization_connections["orgA"] == {"c2"}
    assert mgr.channel_subscribers["ch1"] == {"c2"}


@pytest.mark.asyncio
async def test_unsubscribe_evicts_empty_channel_entry():
    mgr = EnhancedConnectionManager()
    _register(mgr, user_id="u1", org_id="orgA", channels=["ch1"], conn_id="c1")

    assert "ch1" in mgr.channel_subscribers

    await mgr.unsubscribe_from_channel("c1", "ch1")

    assert "ch1" not in mgr.channel_subscribers
