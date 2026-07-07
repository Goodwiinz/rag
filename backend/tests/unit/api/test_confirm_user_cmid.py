"""The confirm/resume assistant idempotency key must derive from the
interrupted turn's OWN user client_message_id (carried through the confirm
request), not the latest user row — otherwise a turn the user sends while a
confirmation is pending becomes "latest" and the resumed assistant collides
with that new turn's assistant row (one answer silently dropped).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.agent.streaming import _resolve_confirm_user_cmid

pytestmark = pytest.mark.unit


async def test_prefers_request_cmid_over_latest_user_row():
    # request carries turn A's cmid; a concurrent turn B is the latest user row.
    request_body = SimpleNamespace(thread_id="t1", client_message_id="turn-A")
    with patch(
        "src.api.agent.streaming._latest_user_client_message_id",
        new=AsyncMock(return_value="turn-B-latest"),
    ) as latest:
        result = await _resolve_confirm_user_cmid(request_body, db=object())

    assert result == "turn-A"  # NOT turn-B-latest → no collision
    latest.assert_not_awaited()


async def test_falls_back_to_latest_when_request_has_no_cmid():
    # Legacy client sends only {thread_id, confirmed}.
    request_body = SimpleNamespace(thread_id="t1", client_message_id=None)
    with patch(
        "src.api.agent.streaming._latest_user_client_message_id",
        new=AsyncMock(return_value="latest-cmid"),
    ) as latest:
        result = await _resolve_confirm_user_cmid(request_body, db=object())

    assert result == "latest-cmid"
    latest.assert_awaited_once()


async def test_missing_attribute_falls_back():
    # Request object without the field at all (older schema) still works.
    request_body = SimpleNamespace(thread_id="t1")
    with patch(
        "src.api.agent.streaming._latest_user_client_message_id",
        new=AsyncMock(return_value="latest-cmid"),
    ):
        result = await _resolve_confirm_user_cmid(request_body, db=object())

    assert result == "latest-cmid"
