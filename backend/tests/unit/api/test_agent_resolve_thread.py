"""``create_if_missing`` behavior of ``_resolve_thread``.

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
        from src.services.agent.agent_execution_service import _resolve_thread

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
        from src.services.agent.agent_execution_service import _resolve_thread

        workspace = Mock()
        workspace.id = "ws-1"
        db = _db_with_thread_lookup(thread=None, workspace=workspace)

        thread, _ = await _resolve_thread(db, _mock_user(), _request())

        assert thread is not None
        assert db.add.call_count == 2  # Conversation + Thread
        db.commit.assert_awaited_once()


class TestResolveThreadFiltersSoftDeleted:
    """The thread lookup must never resolve a soft-deleted thread (or one under
    a soft-deleted conversation/workspace) — a stale tab / SSE retry would
    otherwise persist a new turn into a deleted thread."""

    async def test_lookup_filters_out_soft_deleted_rows(self):
        from src.services.agent.agent_execution_service import _resolve_thread

        captured = {}

        def _capture(stmt, *a, **kw):
            captured["stmt"] = str(
                stmt.compile(compile_kwargs={"literal_binds": False})
            )
            return MagicMock(scalar_one_or_none=Mock(return_value=None))

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_capture)

        thread, conversation_id = await _resolve_thread(
            db, _mock_user(), _request(), create_if_missing=False
        )

        assert thread is None
        assert conversation_id == ""
        sql = captured["stmt"].lower()
        # Thread, Conversation, and Workspace must each be filtered on is_deleted.
        assert sql.count("is_deleted = false") >= 3, sql

    async def test_create_if_missing_workspace_pick_excludes_soft_deleted(self):
        """The create-on-miss workspace pick must exclude soft-deleted
        workspaces, so a fresh Conversation+Thread is never parented under a
        deleted workspace. With only a soft-deleted workspace present the pick
        finds nothing → thread stays None → returns (None, "")."""
        from src.services.agent.agent_execution_service import _resolve_thread

        captured = []

        def _capture(stmt, *a, **kw):
            captured.append(str(stmt.compile(compile_kwargs={"literal_binds": False})))
            # Thread lookup misses; workspace pick also misses (only a
            # soft-deleted workspace exists, which the filter excludes).
            return MagicMock(scalar_one_or_none=Mock(return_value=None))

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_capture)
        db.add = Mock()
        db.commit = AsyncMock()

        thread, conversation_id = await _resolve_thread(
            db, _mock_user(), _request(), create_if_missing=True
        )

        assert thread is None
        assert conversation_id == ""
        db.add.assert_not_called()  # no workspace → nothing created
        db.commit.assert_not_awaited()
        # Second execute() is the workspace pick; it must filter is_deleted.
        assert len(captured) == 2, captured
        ws_sql = captured[1].lower()
        assert "is_deleted = false" in ws_sql, ws_sql
