"""Soft-deleting a parent conversation/workspace must revoke thread + message access.

``delete_conversation`` / ``delete_workspace`` set only their OWN ``is_deleted``
flag — they do not cascade to child threads. ``get_thread`` is the shared funnel
for create_message / list_messages / thread update+delete, so it must reject a
thread whose parent conversation or workspace is soft-deleted. ``get_message``
(its own thread lookup) must do the same for the message id path.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.models import ChatMessage, MessageRole
from src.models.conversation import Conversation
from src.models.workspace import Workspace
from src.services.threads.chat_service import ChatService

pytestmark = pytest.mark.integration


async def _parents(db_session, thread):
    conversation = (
        await db_session.execute(
            select(Conversation).where(Conversation.id == thread.conversation_id)
        )
    ).scalar_one()
    workspace = (
        await db_session.execute(
            select(Workspace).where(Workspace.id == conversation.workspace_id)
        )
    ).scalar_one()
    return conversation, workspace


async def test_get_thread_none_when_parent_conversation_soft_deleted(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    conversation, _ = await _parents(db_session, thread)
    service = ChatService(db_session)

    assert (await service.get_thread(thread.id, user.id)) is not None  # live guard

    conversation.is_deleted = True
    await db_session.commit()

    assert (await service.get_thread(thread.id, user.id)) is None


async def test_get_thread_none_when_workspace_soft_deleted(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    _, workspace = await _parents(db_session, thread)
    service = ChatService(db_session)

    workspace.is_deleted = True
    await db_session.commit()

    assert (await service.get_thread(thread.id, user.id)) is None


async def test_get_thread_returns_thread_when_parents_live(
    db_session, thread_factory, user_factory
):
    """Guard against over-blocking: live parents must still resolve."""
    user = await user_factory()
    thread = await thread_factory(user=user)
    service = ChatService(db_session)

    assert (await service.get_thread(thread.id, user.id)) is not None


async def test_get_conversation_none_when_workspace_soft_deleted(
    db_session, thread_factory, user_factory
):
    """``get_conversation`` filters its own ``is_deleted`` but must ALSO reject
    a live conversation whose parent workspace was soft-deleted (delete_workspace
    flags only its own row)."""
    user = await user_factory()
    thread = await thread_factory(user=user)
    conversation, workspace = await _parents(db_session, thread)
    service = ChatService(db_session)

    # Live workspace: resolves.
    assert (await service.get_conversation(conversation.id, user.id)) is not None

    # Conversation itself is NOT deleted — only the parent workspace.
    workspace.is_deleted = True
    await db_session.commit()

    assert (await service.get_conversation(conversation.id, user.id)) is None


async def test_get_message_none_when_parent_conversation_soft_deleted(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    msg = ChatMessage(
        thread_id=thread.id,
        user_id=user.id,
        role=MessageRole.USER,
        content="hello",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    db_session.info["_created"]["chat_messages"].append(msg.id)

    conversation, workspace = await _parents(db_session, thread)
    service = ChatService(db_session)

    assert (await service.get_message(msg.id, user.id)) is not None  # live guard

    conversation.is_deleted = True
    await db_session.commit()
    assert (await service.get_message(msg.id, user.id)) is None

    conversation.is_deleted = False
    workspace.is_deleted = True
    await db_session.commit()
    assert (await service.get_message(msg.id, user.id)) is None
