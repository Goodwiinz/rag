"""Thread/conversation WebSocket events must not cross organization boundaries.

ThreadEventService broadcasts to ``thread:{id}`` / ``conversation:{id}`` /
``user:{uid}:threads`` channels. These are NOT admin-only, so any authenticated
user can subscribe to another tenant's channel mid-session (the SUBSCRIBE
handler gates only ``_ADMIN_ONLY_CHANNELS``). Before the fix the broadcasts
omitted ``target_organization`` → ``ConnectionInfo.should_receive_message``
SKIPS its org gate when that field is None → an org-B subscriber received org-A
thread payloads (incl. ``content_preview``). The fix sets
``target_organization=str(organization_id)`` on every broadcast so the gate
rejects cross-org delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.services.threads.thread_event_service import ThreadEventService
from src.services.websocket.websocket_manager import (
    ConnectionInfo,
    EnhancedConnectionManager,
)

pytestmark = pytest.mark.unit

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"
THREAD = "33333333-3333-3333-3333-333333333333"
CONV = "44444444-4444-4444-4444-444444444444"


def _conn(org_id: str, channels):
    return ConnectionInfo(
        user_id="u-1",
        organization_id=org_id,
        connection_id=f"c-{org_id}",
        websocket=object(),
        connected_at=datetime.now(timezone.utc),
        last_heartbeat=datetime.now(timezone.utc),
        subscribed_channels=set(channels),
        client_info={"role": "USER"},
    )


def _svc_with_subscriber(org_id: str, channels):
    """A ThreadEventService whose manager has one subscriber on `channels`.

    send_message_to_connection is spied so we can see whether the org gate let
    the message through and inspect the message that would have been sent.
    """
    mgr = EnhancedConnectionManager()
    conn = _conn(org_id, channels)
    mgr.active_connections[conn.connection_id] = conn
    for ch in channels:
        mgr.channel_subscribers[ch].add(conn.connection_id)
    mgr.send_message_to_connection = AsyncMock()

    svc = ThreadEventService()
    svc._manager = mgr
    return svc, mgr, conn


@pytest.mark.asyncio
async def test_message_created_blocked_for_other_org():
    # Attacker connection in ORG_B subscribed to ORG_A's thread channel.
    svc, mgr, _ = _svc_with_subscriber(ORG_B, [f"thread:{THREAD}"])
    await svc.broadcast_message_created(
        message_id="m-1",
        thread_id=THREAD,
        conversation_id=CONV,
        user_id="author",
        organization_id=ORG_A,
        role="assistant",
        content_preview="secret tenant content",
    )
    mgr.send_message_to_connection.assert_not_awaited()  # cross-org → dropped


@pytest.mark.asyncio
async def test_message_created_delivered_to_same_org():
    svc, mgr, conn = _svc_with_subscriber(ORG_A, [f"thread:{THREAD}"])
    await svc.broadcast_message_created(
        message_id="m-1",
        thread_id=THREAD,
        conversation_id=CONV,
        user_id="author",
        organization_id=ORG_A,
        role="assistant",
        content_preview="secret tenant content",
    )
    mgr.send_message_to_connection.assert_awaited_once()
    sent_msg = mgr.send_message_to_connection.await_args.args[1]
    assert sent_msg.target_organization == ORG_A


@pytest.mark.asyncio
async def test_none_org_fails_closed():
    # str(None) == "None" matches no real-org connection → no delivery.
    svc, mgr, _ = _svc_with_subscriber(ORG_A, [f"thread:{THREAD}"])
    await svc.broadcast_message_created(
        message_id="m-1",
        thread_id=THREAD,
        conversation_id=CONV,
        user_id="author",
        organization_id=str(None),
        role="assistant",
        content_preview="x",
    )
    mgr.send_message_to_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_broadcasts_set_target_organization():
    """Every broadcast_* method must stamp target_organization=str(org).

    Subscribe a matching-org connection on every channel family so each
    message is delivered and we can capture target_organization. A method that
    forgets the stamp would emit None and (a) skip the gate / (b) fail this
    assert.
    """
    channels = [
        f"thread:{THREAD}",
        f"conversation:{CONV}",
        "user:author:threads",
    ]
    svc, mgr, _ = _svc_with_subscriber(ORG_A, channels)
    sent: list = []
    mgr.send_message_to_connection = AsyncMock(
        side_effect=lambda cid, msg: sent.append(msg)
    )

    await svc.broadcast_thread_created(THREAD, CONV, "author", ORG_A, title="t")
    await svc.broadcast_thread_updated(THREAD, CONV, "author", ORG_A, {"a": 1})
    await svc.broadcast_thread_deleted(THREAD, CONV, "author", ORG_A)
    await svc.broadcast_message_created(
        "m-1", THREAD, CONV, "author", ORG_A, "assistant"
    )
    await svc.broadcast_message_updated("m-1", THREAD, CONV, ORG_A, {"a": 1})
    await svc.broadcast_conversation_updated(CONV, "author", ORG_A, {"a": 1})
    await svc.broadcast_threads_bulk_updated([THREAD], "resolved", "author", ORG_A)

    assert len(sent) == 7  # every method delivered
    assert all(m.target_organization == ORG_A for m in sent)
