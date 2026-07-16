"""Characterize conversation_service.py (Task 4.3 consolidation).

Covers the measured divergences: ``order_pinned_first`` (list ordering) and
the ``stamp_deleted_at``/``require_admin`` delete flags (see the module
docstring + docs/plans/2026-07-15-maintainability-foundation.md Task 4.3).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.conversation import Conversation
from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.schemas.chat import ConversationCreate, ConversationUpdate
from src.services.threads import conversation_service

pytestmark = pytest.mark.integration


async def _make_workspace(db_session, owner):
    ws = Workspace(name="ws", owner_id=owner.id, organization_id=owner.organization_id)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    return ws


async def test_create_conversation_not_found_vs_forbidden(db_session, user_factory):
    owner = await user_factory()
    viewer = await user_factory()
    ws = await _make_workspace(db_session, owner)
    db_session.add(
        WorkspaceMember(
            workspace_id=ws.id, user_id=viewer.id, role=WorkspaceRole.VIEWER
        )
    )
    await db_session.commit()

    assert (
        await conversation_service.create_conversation(
            db_session, ConversationCreate(workspace_id=uuid4(), title="t"), owner.id
        )
    ) is None  # workspace not found

    with pytest.raises(PermissionError):
        await conversation_service.create_conversation(
            db_session, ConversationCreate(workspace_id=ws.id, title="t"), viewer.id
        )


async def test_list_conversations_order_pinned_first_flag(db_session, user_factory):
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)

    older_pinned = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="pinned"), owner.id
    )
    newer_unpinned = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="fresh"), owner.id
    )
    older_pinned.is_pinned = True
    await db_session.commit()

    pinned_first, _total, _counts = await conversation_service.list_conversations(
        db_session, ws.id, owner.id, order_pinned_first=True
    )
    assert pinned_first[0].id == older_pinned.id

    activity_only, _total, _counts = await conversation_service.list_conversations(
        db_session, ws.id, owner.id, order_pinned_first=False
    )
    assert activity_only[0].id == newer_unpinned.id


async def test_list_conversations_returns_none_for_missing_workspace(
    db_session, user_factory
):
    owner = await user_factory()
    assert (
        await conversation_service.list_conversations(db_session, uuid4(), owner.id)
    ) is None


async def test_update_conversation_rejects_mismatched_workspace_id(
    db_session, user_factory
):
    owner = await user_factory()
    ws_a = await _make_workspace(db_session, owner)
    ws_b = await _make_workspace(db_session, owner)
    conv = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws_b.id, title="t"), owner.id
    )

    assert (
        await conversation_service.update_conversation(
            db_session,
            conv.id,
            ConversationUpdate(title="new"),
            owner.id,
            workspace_id=ws_a.id,
        )
    ) is None

    updated = await conversation_service.update_conversation(
        db_session,
        conv.id,
        ConversationUpdate(title="new"),
        owner.id,
        workspace_id=ws_b.id,
    )
    assert updated.title == "new"


async def test_delete_conversation_flags(db_session, user_factory):
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)
    conv_stamped = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="a"), owner.id
    )
    conv_unstamped = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="b"), owner.id
    )

    assert await conversation_service.delete_conversation(
        db_session, conv_stamped.id, owner.id, stamp_deleted_at=True
    )
    assert conv_stamped.deleted_at is not None

    assert await conversation_service.delete_conversation(
        db_session, conv_unstamped.id, owner.id, stamp_deleted_at=False
    )
    assert conv_unstamped.deleted_at is None


async def test_delete_conversation_require_admin_flag(db_session, user_factory):
    owner = await user_factory()
    editor = await user_factory()
    ws = await _make_workspace(db_session, owner)
    db_session.add(
        WorkspaceMember(
            workspace_id=ws.id, user_id=editor.id, role=WorkspaceRole.EDITOR
        )
    )
    await db_session.commit()
    conv = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="a"), owner.id
    )
    db_session.expire(ws, ["members"])

    # require_admin=False (router-canonical): editor rights suffice.
    assert await conversation_service.delete_conversation(
        db_session, conv.id, editor.id, require_admin=False
    )

    conv2 = await conversation_service.create_conversation(
        db_session, ConversationCreate(workspace_id=ws.id, title="b"), owner.id
    )
    db_session.expire(ws, ["members"])
    # require_admin=True (old ChatService default): editor-only is not enough.
    with pytest.raises(PermissionError):
        await conversation_service.delete_conversation(
            db_session, conv2.id, editor.id, require_admin=True
        )
