"""Regression coverage for concurrent-safe ChatService thread counters."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from src.models.chat_message import ChatMessage
from src.models.conversation import Conversation
from src.models.thread import Thread
from src.models.workspace import Workspace
from src.schemas.chat import ChatMessageCreate, MessageRole
from src.services.threads.chat_service import ChatService

pytestmark = pytest.mark.unit


@pytest.fixture
async def db() -> AsyncGenerator[tuple[AsyncSession, uuid.UUID, uuid.UUID], None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Thread.__table__.create)
        await conn.run_sync(ChatMessage.__table__.create)
        await conn.run_sync(Workspace.__table__.create)
        await conn.run_sync(Conversation.__table__.create)

    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        session.add(
            Workspace(
                id=workspace_id,
                name="workspace",
                owner_id=user_id,
                organization_id=uuid.uuid4(),
                members=[],
            )
        )
        session.add(
            Conversation(
                id=conversation_id,
                workspace_id=workspace_id,
                title="conversation",
                created_by_id=user_id,
            )
        )
        session.add(
            Thread(
                id=thread_id,
                conversation_id=conversation_id,
                created_by_id=user_id,
                message_count=2,
                token_count=10,
            )
        )
        await session.commit()
        yield session, user_id, thread_id
    await engine.dispose()


async def _thread_row(session: AsyncSession, thread_id: uuid.UUID) -> Thread:
    row = (
        await session.execute(select(Thread).where(Thread.id == thread_id))
    ).scalar_one()
    await session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_user_and_assistant_writers_increment_db_counters(
    db: tuple[AsyncSession, uuid.UUID, uuid.UUID],
) -> None:
    session, user_id, thread_id = db
    service = ChatService(session)
    thread = (
        await session.execute(
            select(Thread)
            .options(
                selectinload(Thread.conversation).selectinload(Conversation.workspace)
            )
            .where(Thread.id == thread_id)
        )
    ).scalar_one()
    set_committed_value(thread.conversation.workspace, "members", [])

    with patch.object(service, "get_thread", new=AsyncMock(return_value=thread)):
        user_message = await service.create_message(
            ChatMessageCreate(
                thread_id=thread_id,
                role=MessageRole.USER,
                content="hello",
            ),
            user_id,
        )

    assert user_message is not None
    row = await _thread_row(session, thread_id)
    assert row.message_count == 3
    assert row.token_count > 10

    with patch(
        "src.services.threads.thread_summarization_service.enqueue_summarization"
    ) as enqueue:
        await service.create_assistant_message(
            thread_id=thread_id,
            content="answer",
            token_count=7,
        )

    row = await _thread_row(session, thread_id)
    assert row.message_count == 4
    assert row.token_count > 17
    enqueue.assert_called_once_with(thread_id)
