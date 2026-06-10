"""WebSocket messages must not cross organization boundaries.

Document/job status updates are queued onto shared broadcast channels
(``document_processing``/``job_status``); before the fix any connection
subscribed to those channels received every tenant's payload. The
``target_organization`` gate + per-(channel, org) batching close that, and
the channel-permission gate stops non-admins subscribing to admin channels.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.websocket.websocket_manager import (
    ConnectionInfo,
    MessageType,
    WebSocketMessage,
    _ADMIN_ONLY_CHANNELS,
)

pytestmark = pytest.mark.unit


def _conn(org_id: str, channels=("document_processing",), role="USER"):
    return ConnectionInfo(
        user_id="u-1",
        organization_id=org_id,
        connection_id="c-1",
        websocket=object(),
        connected_at=datetime.now(timezone.utc),
        last_heartbeat=datetime.now(timezone.utc),
        subscribed_channels=set(channels),
        client_info={"role": role},
    )


def _msg(target_org):
    return WebSocketMessage(
        type=MessageType.DOCUMENT_PROCESSING,
        data={"document_id": "d-1"},
        timestamp=datetime.now(timezone.utc),
        target_channels=["document_processing"],
        target_organization=target_org,
    )


def test_message_blocked_for_other_org():
    conn = _conn("org-A")
    assert conn.should_receive_message(_msg("org-B")) is False


def test_message_delivered_to_matching_org():
    conn = _conn("org-A")
    assert conn.should_receive_message(_msg("org-A")) is True


def test_message_without_target_org_is_not_blocked_by_gate():
    # Gate semantics: target_organization=None means "genuinely global" (e.g.
    # system notifications) and falls through to the channel-subscription
    # check. The fail-CLOSED guarantee for tenant payloads lives at the
    # PRODUCER (status_update_service skips the channel broadcast when a
    # document/job has no org) — see test_status_update_batch_scoping, not
    # here, so this None=global gate behavior is correct.
    conn = _conn("org-A")
    assert conn.should_receive_message(_msg(None)) is True


def test_unsubscribed_channel_still_blocked_even_with_org_match():
    conn = _conn("org-A", channels=("job_status",))
    assert conn.should_receive_message(_msg("org-A")) is False


# --- channel permission gate -------------------------------------------------


def test_can_subscribe_gate():
    from src.api.realtime.websocket_v2 import _can_subscribe_to_channel

    assert _can_subscribe_to_channel("document_processing", "USER") is True
    assert _can_subscribe_to_channel("admin_alerts", "USER") is False
    assert _can_subscribe_to_channel("admin_alerts", "ADMIN") is True
    assert _can_subscribe_to_channel("system_status", "admin") is True  # case-insensitive
    assert _can_subscribe_to_channel("not_a_real_channel", "ADMIN") is False


def test_admin_only_channel_set_matches_permission_map():
    """The manager-side constant must stay in sync with the v2 permission map."""
    from src.api.realtime.websocket_v2 import Channel, _get_channel_permissions

    admin = {c.value for c in Channel if _get_channel_permissions(c) == "admin"}
    assert admin == _ADMIN_ONLY_CHANNELS


# --- Redis cross-instance round-trip (sev-9 gap) -----------------------------


def test_asdict_not_json_serializable_but_explicit_payload_roundtrips_org():
    """Documents WHY the publish path hand-builds a dict instead of asdict():
    asdict leaves Enum/datetime raw → json.dumps raises. The explicit payload
    round-trips target_organization so the org gate holds across workers."""
    import json
    from dataclasses import asdict
    from datetime import datetime

    msg = _msg("org-A")

    with pytest.raises(TypeError):  # the old asdict() path could not encode
        json.dumps(asdict(msg))

    # The explicit payload the publisher builds (websocket_manager.py:619-626).
    payload = {
        "type": msg.type.value,
        "data": msg.data,
        "timestamp": msg.timestamp.isoformat(),
        "message_id": msg.message_id,
        "priority": msg.priority.value,
        "target_channels": msg.target_channels,
        "target_organization": msg.target_organization,
    }
    rebuilt = json.loads(json.dumps(payload))

    # The receiver reconstruction (websocket_manager.py:866-873).
    out = WebSocketMessage(
        type=MessageType(rebuilt["type"]),
        data=rebuilt["data"],
        timestamp=datetime.fromisoformat(rebuilt["timestamp"]),
        message_id=rebuilt.get("message_id") or rebuilt.get("id"),
        target_channels=rebuilt.get("target_channels", []),
        target_organization=rebuilt.get("target_organization"),
    )
    assert out.target_organization == "org-A"  # org scope survives the hop
    assert out.message_id == msg.message_id


# --- mid-session SUBSCRIBE gate (sev-8 gap) ----------------------------------


def _mgr_with_conn(role):
    import json as _json
    from unittest.mock import AsyncMock

    from src.services.websocket.websocket_manager import EnhancedConnectionManager

    mgr = EnhancedConnectionManager()
    conn = _conn("org-A", role=role)
    mgr.active_connections[conn.connection_id] = conn
    mgr.subscribe_to_channel = AsyncMock()
    mgr.send_message_to_connection = AsyncMock()
    return mgr, conn, _json


@pytest.mark.asyncio
async def test_mid_session_subscribe_denies_admin_channel_for_non_admin():
    mgr, conn, _json = _mgr_with_conn("USER")
    await mgr.handle_client_message(
        conn.connection_id,
        _json.dumps({"type": "subscribe", "data": {"channel": "admin_alerts"}}),
    )
    mgr.subscribe_to_channel.assert_not_awaited()  # denied
    mgr.send_message_to_connection.assert_awaited()  # explicit denial frame
    sent = mgr.send_message_to_connection.await_args.args[1]
    assert sent.type == MessageType.ERROR
    assert sent.data["error"] == "subscription_denied"


@pytest.mark.asyncio
async def test_mid_session_subscribe_allows_admin_channel_for_admin():
    mgr, conn, _json = _mgr_with_conn("ADMIN")
    await mgr.handle_client_message(
        conn.connection_id,
        _json.dumps({"type": "subscribe", "data": {"channel": "admin_alerts"}}),
    )
    mgr.subscribe_to_channel.assert_awaited_once()


@pytest.mark.asyncio
async def test_mid_session_subscribe_allows_normal_channel_for_user():
    mgr, conn, _json = _mgr_with_conn("USER")
    await mgr.handle_client_message(
        conn.connection_id,
        _json.dumps({"type": "subscribe", "data": {"channel": "document_processing"}}),
    )
    mgr.subscribe_to_channel.assert_awaited_once()  # normal channel allowed
