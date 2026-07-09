"""Cross-worker WebSocket fan-out must actually reach other workers/replicas.

The connection manager keeps per-process in-memory registries, so with more
than one gunicorn worker (the deployed default is 2) a push produced on worker
A only reaches sockets on worker A unless it is forwarded over Redis. Two bugs
broke that silently:

* ``broadcast_to_user`` / ``broadcast_to_organization`` never published to
  Redis at all (local-only), so targeted pushes never crossed workers (FO1).
* ``instance_id`` was never assigned, so the listener's self-filter compared
  ``"unknown" == "unknown"`` and dropped EVERY sibling worker's broadcast, and
  the listener re-published forwarded messages (amplification once fixed) (FO2/FO3).

These tests pin the fix: real per-instance id, all three broadcast_* publish,
and the listener delivers to LOCAL subscribers only (never re-publishes).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.services.websocket.websocket_manager import (
    ConnectionInfo,
    EnhancedConnectionManager,
    MessageType,
    WebSocketMessage,
)

pytestmark = pytest.mark.unit


class FakeWS:
    """Minimal WebSocket stand-in that records what was sent."""

    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, *args, **kwargs):
        pass


def _now():
    return datetime.now(timezone.utc)


def _msg(target_org=None, msg_type=MessageType.SYSTEM_NOTIFICATION, channels=None):
    return WebSocketMessage(
        type=msg_type,
        data={"x": 1},
        timestamp=_now(),
        target_channels=list(channels or []),
        target_organization=target_org,
    )


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


def test_instance_id_assigned_and_unique():
    a = EnhancedConnectionManager()
    b = EnhancedConnectionManager()
    assert isinstance(a.instance_id, str) and a.instance_id
    assert a.instance_id != b.instance_id  # one id per worker process


@pytest.mark.asyncio
async def test_broadcast_to_user_delivers_local_and_publishes_to_cluster():
    # FO1: broadcast_to_user must reach the local socket AND cross to other workers.
    mgr = EnhancedConnectionManager()
    mgr.redis_client = AsyncMock()
    _, ws = _register(mgr, user_id="u1", org_id="orgA")

    await mgr.broadcast_to_user("u1", _msg(target_org=None))

    assert len(ws.sent) == 1  # local delivery
    mgr.redis_client.publish.assert_awaited_once()  # cross-worker publish restored
    _, raw = mgr.redis_client.publish.await_args.args
    payload = json.loads(raw)
    assert payload["kind"] == "user"
    assert payload["target"] == "u1"
    assert payload["source_instance"] == mgr.instance_id


@pytest.mark.asyncio
async def test_broadcast_to_organization_publishes_with_org_kind():
    mgr = EnhancedConnectionManager()
    mgr.redis_client = AsyncMock()
    _register(mgr, user_id="u1", org_id="orgA")

    await mgr.broadcast_to_organization("orgA", _msg(target_org="orgA"))

    mgr.redis_client.publish.assert_awaited_once()
    payload = json.loads(mgr.redis_client.publish.await_args.args[1])
    assert payload["kind"] == "organization"
    assert payload["target"] == "orgA"


@pytest.mark.asyncio
async def test_broadcast_to_user_respects_org_gate():
    # A message addressed to orgB must not reach an orgA socket, even for the same user id.
    mgr = EnhancedConnectionManager()  # no redis -> single-instance
    _, ws = _register(mgr, user_id="u1", org_id="orgA")

    await mgr.broadcast_to_user("u1", _msg(target_org="orgB"))

    assert ws.sent == []


@pytest.mark.asyncio
async def test_dispatch_cluster_message_delivers_local_only_no_republish():
    # FO2/FO3: a forwarded message reaches the local socket but is NOT re-published.
    mgr = EnhancedConnectionManager()
    mgr.redis_client = AsyncMock()  # so any accidental re-publish is observable
    _, ws = _register(mgr, user_id="u1", org_id="orgA")

    bd = {
        "kind": "user",
        "target": "u1",
        "message": mgr._serialize_for_cluster(_msg(target_org=None)),
        "source_instance": "some-other-worker",
    }
    await mgr._dispatch_cluster_message(bd)

    assert len(ws.sent) == 1  # forwarded to the local socket
    mgr.redis_client.publish.assert_not_awaited()  # no amplification storm


@pytest.mark.asyncio
async def test_dispatch_skips_own_publish():
    mgr = EnhancedConnectionManager()
    _, ws = _register(mgr, user_id="u1", org_id="orgA")

    bd = {
        "kind": "user",
        "target": "u1",
        "message": mgr._serialize_for_cluster(_msg(target_org=None)),
        "source_instance": mgr.instance_id,  # our own broadcast
    }
    await mgr._dispatch_cluster_message(bd)

    assert ws.sent == []  # skipped — we already delivered locally before publishing


@pytest.mark.asyncio
async def test_dispatch_legacy_channel_payload_still_routes():
    # Rolling-deploy back-compat: a pre-fix worker publishes only a bare "channel".
    mgr = EnhancedConnectionManager()
    _, ws = _register(
        mgr, user_id="u1", org_id="orgA", channels=("document_processing",)
    )

    msg = _msg(target_org=None, channels=["document_processing"])
    bd = {
        "channel": "document_processing",  # no "kind"/"target"
        "message": mgr._serialize_for_cluster(msg),
        "source_instance": "old-worker",
    }
    await mgr._dispatch_cluster_message(bd)

    assert len(ws.sent) == 1
