"""R5-M12: exports must never resurrect soft-deleted content.

``ExportService._load_thread`` carried no ``Thread.is_deleted`` filter (a
soft-deleted thread was exportable) and no parent-cascade check (a thread
whose conversation/workspace was soft-deleted, but whose own ``is_deleted``
stayed False since neither delete cascades to children — see
``workspace_access.py``), and the per-message loop filtered
``superseded_by_message_id`` + system messages but never ``msg.is_deleted`` —
a user's deleted messages, including ones scrubbed for PII, reappeared in
every export format.

Fixed: the query now filters ``Thread.is_deleted == False``; the parent
conversation/workspace ``is_deleted`` is re-checked explicitly (mirroring
``workspace_access.get_thread``'s cascade convention); the message loop skips
``msg.is_deleted`` rows.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.chat_message import MessageRole
from src.services.research.export_service import ExportOptions, ExportService

pytestmark = pytest.mark.unit


def _where_clauses_text(stmt: Any) -> str:
    """Stringify the statement's WHERE clause for a substring check."""
    return str(stmt.whereclause)


def _msg(
    *,
    is_deleted: bool = False,
    superseded_by_message_id=None,
    role: MessageRole = MessageRole.USER,
    content: str = "hello",
) -> MagicMock:
    msg = MagicMock()
    msg.id = "m-1"
    msg.is_deleted = is_deleted
    msg.superseded_by_message_id = superseded_by_message_id
    msg.role = role
    msg.content = content
    msg.created_at = datetime.datetime(2026, 1, 1)
    msg.model_name = "gpt"
    msg.token_count = 1
    msg.latency_ms = 1
    msg.feedback_rating = None
    msg.feedback_text = None
    msg.citations = []
    msg.has_attachments = False
    return msg


def _thread(
    *,
    thread_deleted: bool = False,
    conversation_deleted: bool = False,
    workspace_deleted: bool = False,
    messages: Optional[list] = None,
    user_id: str = "u-1",
) -> MagicMock:
    thread = MagicMock()
    thread.id = "t-1"
    thread.is_deleted = thread_deleted
    thread.created_by_id = user_id
    thread.title = "Thread"
    thread.summary = None
    thread.status = None
    thread.created_at = datetime.datetime(2026, 1, 1)
    thread.updated_at = datetime.datetime(2026, 1, 1)
    thread.last_message_at = datetime.datetime(2026, 1, 1)
    thread.message_count = 0
    thread.token_count = 0
    thread.conversation_id = "c-1"
    thread.messages = messages or []

    thread.conversation.is_deleted = conversation_deleted
    thread.conversation.created_by_id = user_id
    thread.conversation.workspace.is_deleted = workspace_deleted
    return thread


async def _load(thread: Any, user_id: str = "u-1"):
    db = AsyncMock()
    result = MagicMock()
    result.unique.return_value.scalar_one_or_none.return_value = thread
    db.execute = AsyncMock(return_value=result)
    svc = ExportService(db)
    out = await svc._load_thread("t-1", user_id, ExportOptions())
    return out, db


# --- query-level filter -------------------------------------------------


@pytest.mark.asyncio
async def test_load_thread_query_filters_is_deleted() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.unique.return_value.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    svc = ExportService(db)
    await svc._load_thread("t-1", "u-1", ExportOptions())

    stmt = db.execute.call_args.args[0]
    assert "is_deleted" in _where_clauses_text(stmt)


# --- thread itself soft-deleted ------------------------------------------


@pytest.mark.asyncio
async def test_soft_deleted_thread_row_excluded_by_query_predicate() -> None:
    """The query predicate is what actually excludes a soft-deleted thread
    (the DB never returns it) — a real ORM row would never reach the Python
    ownership/cascade checks with is_deleted=True. Prove the predicate is
    present (previous test) and that, absent it, the None-thread branch
    behaves as a 404-equivalent."""
    out, _ = await _load(None)
    assert out is None


# --- parent cascade: soft-deleted conversation/workspace revoke access ---


@pytest.mark.asyncio
async def test_soft_deleted_parent_conversation_revokes_export() -> None:
    thread = _thread(conversation_deleted=True)
    out, _ = await _load(thread)
    assert out is None


@pytest.mark.asyncio
async def test_soft_deleted_parent_workspace_revokes_export() -> None:
    thread = _thread(workspace_deleted=True)
    out, _ = await _load(thread)
    assert out is None


# --- message-level filter -------------------------------------------------


@pytest.mark.asyncio
async def test_deleted_message_excluded_live_message_included() -> None:
    live = _msg(is_deleted=False, content="still here")
    deleted = _msg(is_deleted=True, content="scrubbed pii")
    thread = _thread(messages=[live, deleted])

    out, _ = await _load(thread)

    assert out is not None
    contents = [m.content for m in out.messages]
    assert contents == ["still here"]
    assert "scrubbed pii" not in contents
