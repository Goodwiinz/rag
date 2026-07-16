"""``create_if_missing`` behavior of ``_resolve_thread`` / ``_persist_thread_messages``.

Confirm/resume paths pass ``create_if_missing=False`` because their thread
already exists (ownership verified against the checkpoint snapshot) — a
lookup miss there is transient and creating a fresh "Agent Chat" thread
would silently split the conversation. These tests pin both the skip
branch and the default create-on-miss behavior staying intact.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _mock_user():
    user = Mock()
    user.id = "user-rt-1"
    return user


def _db_with_thread_lookup(thread=None, workspace=None):
    """AsyncSession mock: first execute() resolves the thread lookup, the
    second (if reached) resolves the workspace lookup."""
    db = AsyncMock()
    thread_result = MagicMock(scalar_one_or_none=Mock(return_value=thread))
    workspace_result = MagicMock(scalar_one_or_none=Mock(return_value=workspace))
    db.execute = AsyncMock(side_effect=[thread_result, workspace_result])
    db.add = Mock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _request(thread_id="11111111-1111-1111-1111-111111111111"):
    request = Mock()
    request.thread_id = thread_id
    request.messages = []
    request.model = ""
    return request


class TestResolveThreadCreateIfMissing:
    async def test_miss_with_create_if_missing_false_returns_none(self):
        from src.api.agent.jobs import _resolve_thread

        db = _db_with_thread_lookup(thread=None)
        thread, conversation_id = await _resolve_thread(
            db, _mock_user(), _request(), create_if_missing=False
        )

        assert thread is None
        assert conversation_id == ""
        # Only the thread lookup ran — the workspace/create branch must not.
        assert db.execute.await_count == 1
        db.add.assert_not_called()
        db.commit.assert_not_awaited()

    async def test_miss_with_default_still_creates(self):
        """The default path (initial turns) must keep creating on miss."""
        from src.api.agent.jobs import _resolve_thread

        workspace = Mock()
        workspace.id = "ws-1"
        db = _db_with_thread_lookup(thread=None, workspace=workspace)

        thread, _ = await _resolve_thread(db, _mock_user(), _request())

        assert thread is not None
        assert db.add.call_count == 2  # Conversation + Thread
        db.commit.assert_awaited_once()


class TestPersistThreadMessagesCreateIfMissing:
    async def test_skip_persist_on_miss_returns_original_thread_id(self, caplog):
        from src.api.agent.jobs import _persist_thread_messages

        db = _db_with_thread_lookup(thread=None)
        request = _request()

        with caplog.at_level("WARNING"):
            thread_id, conversation_id = await _persist_thread_messages(
                db,
                _mock_user(),
                request,
                "assistant says hi",
                create_if_missing=False,
            )

        # Client still gets its thread_id back; nothing was persisted.
        assert thread_id == request.thread_id
        assert conversation_id == ""
        assert any("persist skipped" in r.message.lower() for r in caplog.records)

    async def test_skip_logs_even_without_thread_id(self, caplog):
        """The skip must never be fully silent — even a thread-less request
        leaves a log record that the turn was not durably stored."""
        from src.api.agent.jobs import _persist_thread_messages

        db = _db_with_thread_lookup(thread=None)
        request = _request(thread_id=None)

        with caplog.at_level("WARNING"):
            thread_id, conversation_id = await _persist_thread_messages(
                db,
                _mock_user(),
                request,
                "assistant says hi",
                create_if_missing=False,
            )

        assert thread_id == ""
        assert conversation_id == ""
        assert any("persist skipped" in r.message.lower() for r in caplog.records)
