"""Verify the partial unique index on chat_messages.(thread_id, client_message_id).

Backs Task 1 of docs/plans/2026-05-13-agent-persist-perf.md. The index is
partial (``WHERE client_message_id IS NOT NULL AND role = 'user'``) so that
NULL client ids and assistant rows remain freely insertable; only user-role
duplicates collide.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.chat_message import ChatMessage, MessageRole


pytestmark = pytest.mark.integration


async def test_duplicate_client_message_id_is_rejected(
    db_session, thread_factory, user_factory
):
    thread = await thread_factory()
    user = await user_factory()
    cmid = uuid4()

    msg1 = ChatMessage(
        thread_id=thread.id,
        user_id=user.id,
        role=MessageRole.USER,
        content="hi",
        client_message_id=cmid,
    )
    db_session.add(msg1)
    await db_session.commit()
    db_session.info["_created"]["chat_messages"].append(msg1.id)

    db_session.add(
        ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content="hi (retry)",
            client_message_id=cmid,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_null_client_message_id_allows_many_rows(db_session, thread_factory):
    thread = await thread_factory()
    created_ids = []
    for _ in range(3):
        msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content="reply",
            client_message_id=None,
        )
        db_session.add(msg)
        await db_session.commit()
        created_ids.append(msg.id)
    db_session.info["_created"]["chat_messages"].extend(created_ids)

    result = await db_session.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id)
    )
    assert len(result.scalars().all()) == 3


async def test_same_client_message_id_on_different_threads_succeeds(
    db_session, thread_factory, user_factory
):
    """Index is scoped to (thread_id, client_message_id) — identical cmids on
    different threads must not collide."""
    user = await user_factory()
    thread_a = await thread_factory(user=user)
    thread_b = await thread_factory(user=user)
    cmid = uuid4()

    for thread in (thread_a, thread_b):
        msg = ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content="hi",
            client_message_id=cmid,
        )
        db_session.add(msg)
        await db_session.commit()
        db_session.info["_created"]["chat_messages"].append(msg.id)

    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.client_message_id == cmid)
        )
    ).scalars().all()
    assert {r.thread_id for r in rows} == {thread_a.id, thread_b.id}


async def test_non_user_role_with_same_client_message_id_succeeds(
    db_session, thread_factory, user_factory
):
    """Partial predicate excludes non-user rows — a user row and a
    non-NULL-cmid assistant/tool row sharing the same key must coexist."""
    user = await user_factory()
    thread = await thread_factory(user=user)
    cmid = uuid4()

    user_msg = ChatMessage(
        thread_id=thread.id,
        user_id=user.id,
        role=MessageRole.USER,
        content="hi",
        client_message_id=cmid,
    )
    db_session.add(user_msg)
    await db_session.commit()
    db_session.info["_created"]["chat_messages"].append(user_msg.id)

    asst_msg = ChatMessage(
        thread_id=thread.id,
        role=MessageRole.ASSISTANT,
        content="hey",
        client_message_id=cmid,
    )
    db_session.add(asst_msg)
    await db_session.commit()
    db_session.info["_created"]["chat_messages"].append(asst_msg.id)
