"""Soft-deleted threads must revoke access to their messages (Batch C, Task C2).

Direct-API only (a soft-deleted thread leaves the sidebar in the UI): every
other read path filters ``Thread.is_deleted``, but ``get_message`` did not — so
GET/PATCH/DELETE on an individual message id kept working after the parent
thread was soft-deleted. ``get_message`` must return ``None`` once the thread is
soft-deleted, and still return the message while the thread is live.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models import ChatMessage, MessageRole
from src.services.threads.chat_service import ChatService

pytestmark = pytest.mark.integration


async def _seed_message(db_session, thread, user) -> ChatMessage:
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
    return msg


async def test_get_message_returns_none_for_soft_deleted_thread(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    msg = await _seed_message(db_session, thread, user)

    service = ChatService(db_session)

    # Live thread: message is accessible.
    assert (await service.get_message(msg.id, user.id)) is not None

    # Soft-delete the thread; the message must become inaccessible.
    thread.is_deleted = True
    await db_session.commit()

    assert (await service.get_message(msg.id, user.id)) is None
