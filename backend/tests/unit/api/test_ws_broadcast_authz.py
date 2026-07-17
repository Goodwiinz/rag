"""Tenant scope on POST /api/v2/ws/broadcast (finding AU2).

An org-scoped ``ADMIN`` is a legitimate broadcast principal, but the message
was built with no ``target_organization`` — so ``broadcast_to_channel`` fanned
out to EVERY tenant's subscribers of that channel with attacker-controlled
message_type + data. These tests pin that ``broadcast_message`` now:

- stamps the caller's own org onto the WebSocketMessage (so
  ``should_receive_message`` gates delivery to the caller's tenant), and
- refuses an explicit foreign-org target with 403.

Direct-call + AsyncMock pattern (see test_user_behavior_org_scope.py).
asyncio_mode=auto, so plain ``async def`` tests run natively.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.realtime import websocket_v2 as ws


def _admin(org_id):
    return SimpleNamespace(
        id="admin-1",
        role=SimpleNamespace(value="admin"),
        organization_id=org_id,
    )


def _request(channel="system_status", target_organizations=None):
    return ws.BroadcastRequest(
        message_type="system_notification",
        data={"title": "hi"},
        channel=channel,
        target_organizations=target_organizations,
    )


async def test_channel_broadcast_stamps_caller_org(monkeypatch):
    """Per-org admin broadcasting to a channel -> message carries their org."""
    mgr = SimpleNamespace(
        broadcast_to_channel=AsyncMock(),
        broadcast_to_user=AsyncMock(),
        broadcast_to_organization=AsyncMock(),
    )
    monkeypatch.setattr(ws, "connection_manager", mgr)

    await ws.broadcast_message(request=_request(), current_user=_admin("org-A"))

    mgr.broadcast_to_channel.assert_awaited_once()
    channel, message = mgr.broadcast_to_channel.await_args.args
    assert channel == "system_status"
    assert message.target_organization == "org-A"


async def test_foreign_org_target_forbidden(monkeypatch):
    """Admin in org-A cannot target org-B; manager never called."""
    mgr = SimpleNamespace(
        broadcast_to_channel=AsyncMock(),
        broadcast_to_user=AsyncMock(),
        broadcast_to_organization=AsyncMock(),
    )
    monkeypatch.setattr(ws, "connection_manager", mgr)

    with pytest.raises(HTTPException) as ei:
        await ws.broadcast_message(
            request=_request(target_organizations=["org-B"]),
            current_user=_admin("org-A"),
        )
    assert ei.value.status_code == 403
    mgr.broadcast_to_channel.assert_not_awaited()
    mgr.broadcast_to_user.assert_not_awaited()
    mgr.broadcast_to_organization.assert_not_awaited()


async def test_own_org_target_allowed(monkeypatch):
    """Admin targeting their OWN org is allowed and stays org-scoped."""
    mgr = SimpleNamespace(
        broadcast_to_channel=AsyncMock(),
        broadcast_to_user=AsyncMock(),
        broadcast_to_organization=AsyncMock(),
    )
    monkeypatch.setattr(ws, "connection_manager", mgr)

    await ws.broadcast_message(
        request=_request(target_organizations=["org-A"]),
        current_user=_admin("org-A"),
    )

    mgr.broadcast_to_organization.assert_awaited_once()
    org_id, message = mgr.broadcast_to_organization.await_args.args
    assert org_id == "org-A"
    assert message.target_organization == "org-A"


async def test_null_org_admin_forbidden(monkeypatch):
    """A null-org admin has no tenant to scope to -> 403 (no str(None) leak)."""
    mgr = SimpleNamespace(
        broadcast_to_channel=AsyncMock(),
        broadcast_to_user=AsyncMock(),
        broadcast_to_organization=AsyncMock(),
    )
    monkeypatch.setattr(ws, "connection_manager", mgr)

    with pytest.raises(HTTPException) as ei:
        await ws.broadcast_message(request=_request(), current_user=_admin(None))
    assert ei.value.status_code == 403
    mgr.broadcast_to_channel.assert_not_awaited()
