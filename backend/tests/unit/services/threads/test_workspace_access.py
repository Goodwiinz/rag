"""Characterize the canonical scope/access funnel (Task 4.3 consolidation).

``backend/tests/api/threads/test_get_thread_soft_deleted_parent.py`` already
covers the soft-deleted-parent cascade guard (via ``ChatService``, which now
delegates here). These tests focus on the capability that consolidation
added: parent-chain scoping (``workspace_id``/``conversation_id``/
``thread_id`` params) that the router's nested routes rely on to 404 a
resource whose id is real but doesn't belong to the path's parent — proven
with cross-org resources sharing identical child ids/titles, not just a bare
404 happy path.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.collection import Collection
from src.models.conversation import Conversation
from src.models.thread import Thread
from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.services.threads import workspace_access

pytestmark = pytest.mark.integration


async def _make_workspace(db_session, owner, *, is_public=False, name="ws"):
    ws = Workspace(
        name=name,
        owner_id=owner.id,
        organization_id=owner.organization_id,
        is_public=is_public,
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    return ws


async def _make_conversation(db_session, workspace, owner, *, title="conv"):
    conv = Conversation(workspace_id=workspace.id, title=title, created_by_id=owner.id)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    db_session.info["_created"]["conversations"].append(conv.id)
    return conv


async def _make_thread(db_session, conversation, owner, *, title="thread"):
    thread = Thread(
        conversation_id=conversation.id, title=title, created_by_id=owner.id
    )
    db_session.add(thread)
    await db_session.commit()
    await db_session.refresh(thread)
    db_session.info["_created"]["threads"].append(thread.id)
    return thread


async def test_get_conversation_rejects_mismatched_workspace_id(
    db_session, user_factory
):
    """Two orgs each own a conversation titled identically — the funnel must
    404 (return None) when the path workspace_id doesn't match the
    conversation's real parent, not silently serve the wrong org's row."""
    owner_a = await user_factory()
    owner_b = await user_factory()
    ws_a = await _make_workspace(db_session, owner_a, name="dup")
    ws_b = await _make_workspace(db_session, owner_b, name="dup")
    conv_b = await _make_conversation(db_session, ws_b, owner_b, title="Q3 Plan")

    # conv_b actually belongs to ws_b; scoping the lookup to ws_a must 404.
    result = await workspace_access.get_conversation(
        db_session, conv_b.id, owner_b.id, workspace_id=ws_a.id
    )
    assert result is None

    # The correct chain still resolves.
    result = await workspace_access.get_conversation(
        db_session, conv_b.id, owner_b.id, workspace_id=ws_b.id
    )
    assert result is not None


async def test_get_thread_rejects_mismatched_conversation_or_workspace_id(
    db_session, user_factory
):
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)
    conv = await _make_conversation(db_session, ws, owner)
    other_conv = await _make_conversation(db_session, ws, owner, title="other")
    thread = await _make_thread(db_session, conv, owner)

    # Wrong conversation_id in the chain -> 404.
    assert (
        await workspace_access.get_thread(
            db_session, thread.id, owner.id, conversation_id=other_conv.id
        )
    ) is None

    # Right conversation, wrong workspace -> 404.
    other_ws = await _make_workspace(db_session, owner, name="other-ws")
    assert (
        await workspace_access.get_thread(
            db_session,
            thread.id,
            owner.id,
            conversation_id=conv.id,
            workspace_id=other_ws.id,
        )
    ) is None

    # Full correct chain resolves.
    assert (
        await workspace_access.get_thread(
            db_session,
            thread.id,
            owner.id,
            conversation_id=conv.id,
            workspace_id=ws.id,
        )
    ) is not None


async def test_get_message_rejects_mismatched_thread_id(
    db_session, thread_factory, user_factory
):
    from src.models import ChatMessage, MessageRole

    user = await user_factory()
    thread = await thread_factory(user=user)
    other_thread = await thread_factory(user=user)

    msg = ChatMessage(
        thread_id=thread.id, user_id=user.id, role=MessageRole.USER, content="hi"
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    db_session.info["_created"]["chat_messages"].append(msg.id)

    assert (
        await workspace_access.get_message(
            db_session, msg.id, user.id, thread_id=other_thread.id
        )
    ) is None
    assert (
        await workspace_access.get_message(
            db_session, msg.id, user.id, thread_id=thread.id
        )
    ) is not None


async def test_get_collection_rejects_mismatched_workspace_id(db_session, user_factory):
    owner = await user_factory()
    ws_a = await _make_workspace(db_session, owner, name="a")
    ws_b = await _make_workspace(db_session, owner, name="b")

    collection = Collection(workspace_id=ws_b.id, name="Papers")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    assert (
        await workspace_access.get_collection(
            db_session, collection.id, owner.id, workspace_id=ws_a.id
        )
    ) is None
    assert (
        await workspace_access.get_collection(
            db_session, collection.id, owner.id, workspace_id=ws_b.id
        )
    ) is not None


async def test_user_can_access_workspace_predicate(db_session, user_factory):
    owner = await user_factory()
    outsider = await user_factory()
    ws = await _make_workspace(db_session, owner, is_public=False)
    ws = await workspace_access.get_workspace(
        db_session, ws.id, owner.id, load_conversations=False, load_collections=False
    )

    assert workspace_access.user_can_access_workspace(ws, owner.id) is True
    assert workspace_access.user_can_access_workspace(ws, outsider.id) is False

    member = WorkspaceMember(
        workspace_id=ws.id, user_id=outsider.id, role=WorkspaceRole.VIEWER
    )
    db_session.add(member)
    await db_session.commit()
    # db_session runs with expire_on_commit=False, so the already-loaded
    # (empty) `.members` collection on `ws` won't pick up the new row on its
    # own — expire just that relationship to force a fresh selectinload
    # (expiring the whole object would also expire `.id`, and a bare
    # attribute access on an expired object triggers a sync lazy-refresh
    # that MissingGreenlets under the async session).
    db_session.expire(ws, ["members"])
    ws = await workspace_access.get_workspace(
        db_session, ws.id, owner.id, load_conversations=False, load_collections=False
    )
    assert workspace_access.user_can_access_workspace(ws, outsider.id) is True

    ws.is_public = True
    stranger_id = uuid4()
    assert workspace_access.user_can_access_workspace(ws, stranger_id) is True

    ws.is_deleted = True
    assert workspace_access.user_can_access_workspace(ws, owner.id) is False


async def test_get_accessible_document_or_none_scopes_by_organization(
    db_session, user_factory, organization_factory
):
    from src.models.document import Document, DocumentType

    org_a = await organization_factory()
    org_b = await organization_factory()
    user_a = await user_factory(organization=org_a)
    user_b = await user_factory(organization=org_b)

    doc_b = Document(
        title="Shared Title",
        filename="doc.pdf",
        file_path="orgb/doc.pdf",
        file_size_bytes=10,
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        organization_id=org_b.id,
        uploaded_by_user_id=user_b.id,
    )
    db_session.add(doc_b)
    await db_session.commit()
    await db_session.refresh(doc_b)

    # org_a's caller must not resolve org_b's document, even with the exact id.
    assert (
        await workspace_access.get_accessible_document_or_none(
            db_session, doc_b.id, user_a.id, org_a.id
        )
    ) is None
    # org_b's own caller resolves it.
    assert (
        await workspace_access.get_accessible_document_or_none(
            db_session, doc_b.id, user_b.id, org_b.id
        )
    ) is not None
