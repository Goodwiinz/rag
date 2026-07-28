"""Integration tests for the split persistence helpers in jobs.py.

The two helpers under test:

* ``persist_user_message`` — INSERT ... ON CONFLICT DO NOTHING against the
  partial unique index on ``chat_messages (thread_id, client_message_id)
  WHERE client_message_id IS NOT NULL AND role = 'user'``. Idempotent: a
  retry with the same ``client_message_id`` must NOT raise and must NOT
  produce a duplicate row.
* ``persist_assistant_message`` — straightforward insert + thread bookkeeping
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
from src.models.chat_message import ChatMessage, MessageRole
from src.services.agent.agent_execution_service import (
    persist_assistant_message,
    persist_user_message,
)

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

    inserted_a = await persist_user_message(db_session, user, req)
    inserted_b = await persist_user_message(db_session, user, req)  # retry
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


async def test_user_then_assistant_round_trip(db_session, thread_factory, user_factory):
    thread = await thread_factory()
    user = await user_factory()
    cmid = uuid4()
    req = AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content="ping", client_message_id=str(cmid))
        ],
        thread_id=str(thread.id),
    )

    await persist_user_message(db_session, user, req)
    await persist_assistant_message(
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
    inserted = await persist_user_message(db_session, user, req)
    assert inserted is False


async def test_assistant_plan_and_token_usage_round_trip(db_session, thread_factory):
    """Plan + per-turn token usage persist on the assistant row and read back
    intact, so a page reload can rehydrate turn provenance from the DB."""
    from uuid import UUID

    thread = await thread_factory()
    plan = [
        {
            "step": 1,
            "description": "Search documents for transformers",
            "tool": "search_documents",
            "args_hint": {"query": "transformers"},
            "depends_on": [],
        },
        {
            "step": 2,
            "description": "Summarize findings",
            "tool": "summarize",
            "args_hint": {},
            "depends_on": [1],
        },
    ]
    usage = {"input_tokens": 1200, "output_tokens": 340}

    msg_id = await persist_assistant_message(
        db_session,
        thread_id=str(thread.id),
        content="answer",
        model_name="gpt-5-mini",
        tool_executions_out=None,
        plan=plan,
        token_usage=usage,
    )

    row = await db_session.get(ChatMessage, UUID(msg_id))
    assert row is not None
    assert row.plan == plan
    assert row.token_usage == usage

    db_session.info["_created"]["chat_messages"].append(row.id)


async def test_assistant_without_provenance_persists_null_columns(
    db_session, thread_factory
):
    """Rows persisted without plan/usage (legacy path, stop path) stay NULL."""
    from uuid import UUID

    thread = await thread_factory()
    msg_id = await persist_assistant_message(
        db_session,
        thread_id=str(thread.id),
        content="answer",
        model_name="gpt-5-mini",
        tool_executions_out=None,
    )

    row = await db_session.get(ChatMessage, UUID(msg_id))
    assert row is not None
    assert row.plan is None
    assert row.token_usage is None

    db_session.info["_created"]["chat_messages"].append(row.id)
