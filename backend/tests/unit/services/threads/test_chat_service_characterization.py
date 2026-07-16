"""Characterize ChatService's CURRENT (pre-4.3) behavior for its existing
callers (backend/src/api/threads/threads.py — the live ``/api/v2/threads``
router — and ``stream_service.py``), locking in the eight measured
divergences from the router-inline ``workspace_routes`` endpoints *before*
Task 4.3 moved the underlying logic into shared resource services.

Per the Task 4.3 amendment (2026-07-16, A2): router semantics are canonical
for the endpoints the router serves, but ChatService's own callers must keep
their observed behavior. These tests pin exactly that — the ChatService
surface must behave identically after the consolidation as it did before it.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.schemas.chat import (
    ChatMessageUpdate,
    ConversationCreate,
    ThreadCreate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from src.services.threads.chat_service import ChatService

pytestmark = pytest.mark.integration


async def _make_workspace(db_session, owner):
    ws = Workspace(name="ws", owner_id=owner.id, organization_id=owner.organization_id)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    return ws


async def test_create_workspace_trusts_requested_org_no_guard(
    db_session, user_factory, organization_factory
):
    """Divergence 1: ChatService.create_workspace has never enforced a
    cross-org guard — unlike the router-inline create endpoint."""
    owner = await user_factory()
    foreign_org = await organization_factory()
    service = ChatService(db_session)

    workspace = await service.create_workspace(
        WorkspaceCreate(name="x", is_public=False, organization_id=foreign_org.id),
        owner.id,
    )
    assert workspace.organization_id == foreign_org.id


async def test_list_workspaces_does_not_filter_deleted_memberships(
    db_session, user_factory
):
    """Divergence 2: a removed (soft-deleted WorkspaceMember) member still
    sees the workspace listed via ChatService — the router-inline list
    endpoint filters this out."""
    owner = await user_factory()
    service = ChatService(db_session)
    workspace = await service.create_workspace(
        WorkspaceCreate(name="x", is_public=False), owner.id
    )

    membership = next(m for m in workspace.members if str(m.user_id) == str(owner.id))
    membership.is_deleted = True
    await db_session.commit()

    workspaces, _total = await service.list_workspaces(owner.id)
    assert workspace.id in [w.id for w in workspaces]


async def test_delete_workspace_never_stamps_deleted_at(db_session, user_factory):
    """Divergence 3: ChatService soft-deletes never set deleted_at (only
    is_deleted); the router-inline delete endpoints always have."""
    owner = await user_factory()
    service = ChatService(db_session)
    workspace = await service.create_workspace(
        WorkspaceCreate(name="x", is_public=False), owner.id
    )

    assert await service.delete_workspace(workspace.id, owner.id) is True
    assert workspace.is_deleted is True
    assert workspace.deleted_at is None


async def test_delete_conversation_never_stamps_deleted_at_and_requires_admin(
    db_session, user_factory
):
    """Divergence 3 + a second permission divergence: ChatService requires
    ADMIN rights to delete a conversation; the router-inline delete
    endpoints require only edit rights."""
    owner = await user_factory()
    editor = await user_factory()
    ws = await _make_workspace(db_session, owner)
    db_session.add(
        WorkspaceMember(
            workspace_id=ws.id, user_id=editor.id, role=WorkspaceRole.EDITOR
        )
    )
    await db_session.commit()

    service = ChatService(db_session)
    conversation = await service.create_conversation(
        ConversationCreate(workspace_id=ws.id, title="c"), owner.id
    )

    # An editor (not admin) is refused by ChatService's own delete rule.
    assert await service.delete_conversation(conversation.id, editor.id) is False

    assert await service.delete_conversation(conversation.id, owner.id) is True
    assert conversation.is_deleted is True
    assert conversation.deleted_at is None


async def test_delete_thread_never_stamps_deleted_at(
    db_session, thread_factory, user_factory
):
    """Divergence 3, for threads."""
    user = await user_factory()
    thread = await thread_factory(user=user)
    service = ChatService(db_session)

    assert await service.delete_thread(thread.id, user.id) is True
    assert thread.is_deleted is True
    assert thread.deleted_at is None


async def test_list_conversations_orders_pinned_first(db_session, user_factory):
    """Divergence 4: ChatService orders pinned conversations to the top; the
    router-inline list endpoint orders by activity only."""
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)
    service = ChatService(db_session)

    older_pinned = await service.create_conversation(
        ConversationCreate(workspace_id=ws.id, title="pinned"), owner.id
    )
    await service.create_conversation(
        ConversationCreate(workspace_id=ws.id, title="fresh"), owner.id
    )
    older_pinned.is_pinned = True
    await db_session.commit()

    conversations, _total = await service.list_conversations(ws.id, owner.id)
    assert conversations[0].id == older_pinned.id


async def test_create_thread_only_flushes_caller_owns_the_commit(
    db_session, user_factory
):
    """Divergence 5: ChatService.create_thread only flushes — a caller that
    never commits (or rolls back) can still discard it. The router-inline
    create endpoints commit immediately."""
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)
    service = ChatService(db_session)
    conversation = await service.create_conversation(
        ConversationCreate(workspace_id=ws.id, title="c"), owner.id
    )

    thread = await service.create_thread(
        ThreadCreate(conversation_id=conversation.id, title="t"), owner.id
    )
    thread_id = thread.id

    await db_session.rollback()

    from sqlalchemy import select

    from src.models.thread import Thread

    row = (
        await db_session.execute(select(Thread).where(Thread.id == thread_id))
    ).scalar_one_or_none()
    assert row is None  # rolled back — never committed by create_thread itself


async def test_delete_message_allows_author_even_as_viewer(
    db_session, thread_factory, user_factory
):
    """Divergence 6: ChatService.delete_message allows the message's AUTHOR
    to delete it even without edit rights; the standalone router endpoint
    requires edit rights and never checks authorship."""
    from src.models import ChatMessage, MessageRole
    from src.models.conversation import Conversation
    from src.models.workspace import Workspace as WorkspaceModel

    owner = await user_factory()
    author_viewer = await user_factory()
    thread = await thread_factory(user=owner)

    from sqlalchemy import select

    conv = (
        await db_session.execute(
            select(Conversation).where(Conversation.id == thread.conversation_id)
        )
    ).scalar_one()
    db_session.add(
        WorkspaceMember(
            workspace_id=conv.workspace_id,
            user_id=author_viewer.id,
            role=WorkspaceRole.VIEWER,
        )
    )
    await db_session.commit()

    msg = ChatMessage(
        thread_id=thread.id,
        user_id=author_viewer.id,
        role=MessageRole.USER,
        content="hi",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    db_session.info["_created"]["chat_messages"].append(msg.id)

    service = ChatService(db_session)
    # A plain viewer can't normally edit, but they authored this message.
    assert await service.delete_message(msg.id, author_viewer.id) is True


async def test_update_workspace_and_delete_workspace_collapse_permission_and_not_found(
    db_session, user_factory
):
    """ChatService's undifferentiated None/False result for not-found vs.
    insufficient-permission (the router distinguishes 404 vs 403; ChatService
    always returns None/False for both)."""
    owner = await user_factory()
    outsider = await user_factory()
    service = ChatService(db_session)
    workspace = await service.create_workspace(
        WorkspaceCreate(name="x", is_public=False), owner.id
    )

    assert (
        await service.update_workspace(uuid4(), WorkspaceUpdate(name="y"), owner.id)
        is None
    )
    assert (
        await service.update_workspace(
            workspace.id, WorkspaceUpdate(name="y"), outsider.id
        )
        is None
    )
    assert await service.delete_workspace(uuid4(), owner.id) is False
    assert await service.delete_workspace(workspace.id, outsider.id) is False
