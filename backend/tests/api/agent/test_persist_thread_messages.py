"""Integration tests for the split persistence helpers in jobs.py.

The two helpers under test:

* ``_persist_user_message`` — INSERT ... ON CONFLICT DO NOTHING against the
  partial unique index on ``chat_messages (thread_id, client_message_id)
  WHERE client_message_id IS NOT NULL AND role = 'user'``. Idempotent: a
  retry with the same ``client_message_id`` must NOT raise and must NOT
  produce a duplicate row.
* ``_persist_assistant_message`` — straightforward insert + thread bookkeeping
  (``message_count`` += 1, ``last_message_at`` = now).

Both helpers commit independently. These tests exercise that behavior
against the local Postgres test DB (the partial unique index is a Postgres
feature, so SQLite cannot model it).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.api.agent.execute import AgentExecuteRequest, AgentMessage
from src.api.agent.jobs import _persist_assistant_message, _persist_user_message
from src.models.chat_message import ChatMessage, MessageRole


pytestmark = pytest.mark.integration


async def test_duplicate_user_turn_is_idempotent(
    db_session, thread_factory, user_factory
):
    thread = await thread_factory()
    user = await user_factory()
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content="hello", client_message_id=str(cmid))
        ],
        thread_id=str(thread.id),
    )

    inserted_a = await _persist_user_message(db_session, user, req)
    inserted_b = await _persist_user_message(db_session, user, req)  # retry
    assert inserted_a is True
    assert inserted_b is False

    count = await db_session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.thread_id == thread.id,
            ChatMessage.role == MessageRole.USER,
        )
    )
    assert count == 1

    # Track for cleanup
    row_ids = (
        (
            await db_session.execute(
                select(ChatMessage.id).where(ChatMessage.thread_id == thread.id)
            )
        )
        .scalars()
        .all()
    )
    db_session.info["_created"]["chat_messages"].extend(row_ids)


async def test_user_then_assistant_round_trip(
    db_session, thread_factory, user_factory
):
    thread = await thread_factory()
    user = await user_factory()
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content="ping", client_message_id=str(cmid))
        ],
        thread_id=str(thread.id),
    )

    await _persist_user_message(db_session, user, req)
    await _persist_assistant_message(
        db_session,
        thread_id=str(thread.id),
        content="pong",
        model_name="gpt-5-mini",
        tool_executions_out=None,
    )

    rows = (
        await db_session.execute(
            select(ChatMessage.role)
            .where(ChatMessage.thread_id == thread.id)
            .order_by(ChatMessage.created_at)
        )
    ).all()
    assert [r[0] for r in rows] == [MessageRole.USER, MessageRole.ASSISTANT]

    # Track for cleanup
    ids = (
        (
            await db_session.execute(
                select(ChatMessage.id).where(ChatMessage.thread_id == thread.id)
            )
        )
        .scalars()
        .all()
    )
    db_session.info["_created"]["chat_messages"].extend(ids)


async def test_user_message_no_op_without_thread_id(db_session, user_factory):
    """When request.thread_id is None, the helper must be a no-op and return False."""
    user = await user_factory()
    req = AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content="orphan", client_message_id=str(uuid4()))
        ],
        thread_id=None,
    )
    inserted = await _persist_user_message(db_session, user, req)
    assert inserted is False
