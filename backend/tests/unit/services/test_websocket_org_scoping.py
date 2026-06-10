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
    # No tenant restriction → falls through to channel-subscription check.
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
