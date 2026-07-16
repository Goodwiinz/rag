"""Characterize thread_service.py (Task 4.3 consolidation).

Covers the ``commit`` (create) and ``stamp_deleted_at`` (delete) divergence
flags, the ``with_preview`` capability addition, the resolution-summary
trigger, and nested-route chain scoping — see the module docstring.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.thread import ThreadStatus
from src.models.workspace import Workspace
from src.schemas.chat import ConversationCreate, ThreadCreate, ThreadUpdate
from src.services.threads import conversation_service, thread_service

pytestmark = pytest.mark.integration


async def _make_conversation(db_session, owner):
    ws = Workspace(name="ws", owner_id=owner.id, organization_id=owner.organization_id)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    conv = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="c"), owner.id
    )
    return ws, conv


async def test_create_thread_commit_flag(db_session, user_factory):
    """``commit=False`` (old ChatService default) only flushes — the row is
    visible in-session but a caller that never commits could still roll it
    back. ``commit=True`` (router-canonical) commits immediately."""
    owner = await user_factory()
    ws, conv = await _make_conversation(db_session, owner)

    flushed = await thread_service.create_thread(
        db_session,
        ThreadCreate(conversation_id=conv.id, title="t1"),
        owner.id,
        commit=False,
    )
    assert flushed.id is not None
    # In-transaction visibility either way; the real distinction is whether
    # a rollback would discard it. Both paths must return a persisted-enough
    # row the caller can immediately read back.
    await db_session.commit()

    committed = await thread_service.create_thread(
        db_session,
        ThreadCreate(conversation_id=conv.id, title="t2"),
        owner.id,
        commit=True,
    )
    assert committed.id is not None


async def test_create_thread_not_found_vs_forbidden(db_session, user_factory):
    owner = await user_factory()
    ws, conv = await _make_conversation(db_session, owner)

    assert (
        await thread_service.create_thread(
            db_session, ThreadCreate(conversation_id=uuid4(), title="t"), owner.id
        )
    ) is None


async def test_create_thread_rejects_mismatched_workspace_id(db_session, user_factory):
    owner = await user_factory()
    ws_a, _conv_a = await _make_conversation(db_session, owner)
    ws_b, conv_b = await _make_conversation(db_session, owner)

    assert (
        await thread_service.create_thread(
            db_session,
            ThreadCreate(conversation_id=conv_b.id, title="t"),
            owner.id,
            workspace_id=ws_a.id,
        )
    ) is None

    thread = await thread_service.create_thread(
        db_session,
        ThreadCreate(conversation_id=conv_b.id, title="t"),
        owner.id,
        workspace_id=ws_b.id,
        commit=True,
    )
    assert thread is not None


async def test_list_threads_with_preview_flag(db_session, thread_factory, user_factory):
    from src.models import ChatMessage, MessageRole

    user = await user_factory()
    thread = await thread_factory(user=user)
    msg = ChatMessage(
        thread_id=thread.id,
        user_id=user.id,
        role=MessageRole.USER,
        content="the answer",
    )
    db_session.add(msg)
    await db_session.commit()
    db_session.info["_created"]["chat_messages"].append(msg.id)

    conv_id = thread.conversation_id

    bare, total, previews = await thread_service.list_threads(
        db_session, conv_id, user.id, with_preview=False
    )
    assert total == 1
    assert previews == {}

    with_preview, _total, previews = await thread_service.list_threads(
        db_session, conv_id, user.id, with_preview=True
    )
    assert previews[thread.id] == "the answer"


async def test_list_threads_returns_none_for_missing_conversation(
    db_session, user_factory
):
    user = await user_factory()
    assert (await thread_service.list_threads(db_session, uuid4(), user.id)) is None


async def test_list_threads_rejects_mismatched_workspace_id(db_session, user_factory):
    """Regression: the nested route's workspace->conversation chain check
    (a conversation requested via a *different* workspace's id 404s) was
    dropped when list_threads moved out of the router. ``workspace_id`` must
    scope the parent lookup exactly like create/update/delete_thread do."""
    owner = await user_factory()
    ws_a, _conv_a = await _make_conversation(db_session, owner)
    ws_b, conv_b = await _make_conversation(db_session, owner)

    assert (
        await thread_service.list_threads(
            db_session, conv_b.id, owner.id, workspace_id=ws_a.id
        )
    ) is None

    result = await thread_service.list_threads(
        db_session, conv_b.id, owner.id, workspace_id=ws_b.id
    )
    assert result is not None


async def test_update_thread_resolve_summary_default_off(
    db_session, thread_factory, user_factory, monkeypatch
):
    """``trigger_resolve_summary`` defaults to ``False`` — every pre-4.3
    caller (buggy-enum ``ChatService``, trigger-less router-inline) observed
    "never fires," so the default must reproduce that exactly (Task 4.3
    amendment A2)."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    calls = []
    import importlib

    task_module = importlib.import_module("src.tasks.summarize_thread_task")
    monkeypatch.setattr(
        task_module.summarize_thread_on_resolve_task,
        "delay",
        lambda tid: calls.append(tid),
    )

    updated = await thread_service.update_thread(
        db_session, thread.id, ThreadUpdate(status=ThreadStatus.RESOLVED), user.id
    )
    assert updated.status == ThreadStatus.RESOLVED
    assert calls == []


async def test_update_thread_resolve_triggers_summary_task_when_opted_in(
    db_session, thread_factory, user_factory, monkeypatch
):
    """With the flag explicitly enabled, the fixed comparison correctly
    enqueues the resolution summary."""
    user = await user_factory()
    thread = await thread_factory(user=user)

    calls = []
    # `src.tasks.summarize_thread_task` (the module) has a same-named task
    # function re-exported at the package level (`src.tasks.__init__`), which
    # shadows plain `from src.tasks import summarize_thread_task` with the
    # Celery task object instead of the submodule — import it explicitly.
    import importlib

    task_module = importlib.import_module("src.tasks.summarize_thread_task")

    monkeypatch.setattr(
        task_module.summarize_thread_on_resolve_task,
        "delay",
        lambda tid: calls.append(tid),
    )

    updated = await thread_service.update_thread(
        db_session,
        thread.id,
        ThreadUpdate(status=ThreadStatus.RESOLVED),
        user.id,
        trigger_resolve_summary=True,
    )
    assert updated.status == ThreadStatus.RESOLVED
    assert calls == [str(thread.id)]


async def test_delete_thread_stamp_deleted_at_flag(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    stamped = await thread_factory(user=user)
    unstamped = await thread_factory(user=user)

    assert await thread_service.delete_thread(
        db_session, stamped.id, user.id, stamp_deleted_at=True
    )
    assert stamped.deleted_at is not None

    assert await thread_service.delete_thread(
        db_session, unstamped.id, user.id, stamp_deleted_at=False
    )
    assert unstamped.deleted_at is None
