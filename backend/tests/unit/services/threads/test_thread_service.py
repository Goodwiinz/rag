"""Characterize thread_service.py (Task 4.3 consolidation; PR 3 Task 3.2 UoW).

Covers the ``stamp_deleted_at`` (delete) divergence flag, the ``with_preview``
capability addition, the resolution-summary trigger, and nested-route chain
scoping — see the module docstring. PR 3 Task 3.2 deleted ``create_thread``'s
``commit`` flag (now unconditionally flush-only, caller owns the commit) and
moved the resolve-summary enqueue to ``enqueue_after_commit`` (fires on the
caller's commit), so the create/resolve tests here characterize that.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Tuple
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.thread import Thread, ThreadStatus
from src.models.user import User
from src.models.workspace import Workspace
from src.schemas.chat import ConversationCreate, ThreadCreate, ThreadUpdate
from src.services.threads import conversation_service, thread_service

pytestmark = pytest.mark.integration


async def _make_conversation(
    db_session: AsyncSession, owner: User
) -> Tuple[Workspace, Conversation]:
    ws = Workspace(name="ws", owner_id=owner.id, organization_id=owner.organization_id)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    conv = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="c"), owner.id
    )
    assert conv is not None
    return ws, conv


async def test_create_thread_flushes_without_committing(
    db_session: AsyncSession, user_factory: Callable[..., Awaitable[User]]
) -> None:
    """PR 3 Task 3.2: ``create_thread`` is unconditionally flush-only (the
    ``commit`` flag was deleted). The row is visible in-session immediately
    (id populated, readable back), but the caller (route / ChatService's
    ``threads.py`` caller) owns the request commit — a caller that never
    commits would roll it back."""
    owner = await user_factory()
    ws, conv = await _make_conversation(db_session, owner)

    flushed = await thread_service.create_thread(
        db_session,
        ThreadCreate(conversation_id=conv.id, title="t1"),
        owner.id,
    )
    assert flushed is not None
    assert flushed.id is not None
    # In-transaction visibility: the same session reads the flushed row back.
    reread = await db_session.get(Thread, flushed.id)
    assert reread is not None
    # The caller owns the commit; do it here so teardown can track + clean up.
    await db_session.commit()
    db_session.info["_created"]["threads"].append(flushed.id)


async def test_create_thread_not_found_vs_forbidden(
    db_session: AsyncSession, user_factory: Callable[..., Awaitable[User]]
) -> None:
    owner = await user_factory()
    ws, conv = await _make_conversation(db_session, owner)

    assert (
        await thread_service.create_thread(
            db_session, ThreadCreate(conversation_id=uuid4(), title="t"), owner.id
        )
    ) is None

    # Non-member targeting a real conversation is indistinguishable from
    # not-found: the access funnel fails closed with None (404 path).
    outsider = await user_factory()
    assert (
        await thread_service.create_thread(
            db_session, ThreadCreate(conversation_id=conv.id, title="t"), outsider.id
        )
    ) is None


async def test_create_thread_rejects_mismatched_workspace_id(
    db_session: AsyncSession, user_factory: Callable[..., Awaitable[User]]
) -> None:
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
    )
    assert thread is not None


async def test_list_threads_with_preview_flag(
    db_session: AsyncSession,
    thread_factory: Callable[..., Awaitable[Thread]],
    user_factory: Callable[..., Awaitable[User]],
) -> None:
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

    bare_result = await thread_service.list_threads(
        db_session, conv_id, user.id, with_preview=False
    )
    assert bare_result is not None
    bare, total, previews = bare_result
    assert total == 1
    assert previews == {}

    preview_result = await thread_service.list_threads(
        db_session, conv_id, user.id, with_preview=True
    )
    assert preview_result is not None
    with_preview, _total, previews = preview_result
    assert previews[thread.id] == "the answer"


async def test_list_threads_returns_none_for_missing_conversation(
    db_session: AsyncSession, user_factory: Callable[..., Awaitable[User]]
) -> None:
    user = await user_factory()
    assert (await thread_service.list_threads(db_session, uuid4(), user.id)) is None


async def test_list_threads_rejects_mismatched_workspace_id(
    db_session: AsyncSession, user_factory: Callable[..., Awaitable[User]]
) -> None:
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
    db_session: AsyncSession,
    thread_factory: Callable[..., Awaitable[Thread]],
    user_factory: Callable[..., Awaitable[User]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert updated is not None
    assert updated.status == ThreadStatus.RESOLVED
    assert calls == []


async def test_update_thread_resolve_triggers_summary_task_when_opted_in(
    db_session: AsyncSession,
    thread_factory: Callable[..., Awaitable[Thread]],
    user_factory: Callable[..., Awaitable[User]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the flag explicitly enabled, the fixed comparison correctly
    enqueues the resolution summary.

    PR 3 Task 3.2: the enqueue moved to ``enqueue_after_commit``, so it now
    fires on the caller's commit (exactly once, dropped on rollback) rather
    than inline at flush — this test verifies that new timing."""
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
    assert updated is not None
    assert updated.status == ThreadStatus.RESOLVED
    # Registered but not yet fired: the leaf flushed, no commit yet.
    assert calls == []
    # The caller's commit drains the enqueue exactly once.
    await db_session.commit()
    assert calls == [str(thread.id)]


async def test_delete_thread_stamp_deleted_at_flag(
    db_session: AsyncSession,
    thread_factory: Callable[..., Awaitable[Thread]],
    user_factory: Callable[..., Awaitable[User]],
) -> None:
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
