from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

# Import the actual definition module (Task 4.2 split list_threads_standalone
# out of the former monolithic workspaces.py into workspace_routes/threads.py).
from src.api.threads.workspace_routes import threads as workspace_routes
from src.models.thread import ThreadStatus


@pytest.mark.asyncio
async def test_standalone_thread_list_returns_latest_message_preview() -> None:
    conversation_id = uuid4()
    thread_id = uuid4()
    now = datetime.now(timezone.utc)

    # Task 4.3: list_threads_standalone delegates to
    # thread_service.list_threads, which resolves the parent conversation
    # through the shared workspace_access.get_conversation funnel — a single
    # query eager-loading conversation.workspace (needed for the access
    # check), not a separate conversation-then-workspace pair of mocked
    # calls.
    workspace = MagicMock()
    workspace.is_deleted = False
    workspace.is_public = True
    conversation = SimpleNamespace(id=conversation_id, workspace=workspace)
    thread = SimpleNamespace(
        id=thread_id,
        conversation_id=conversation_id,
        title="Preview thread",
        summary=None,
        status=ThreadStatus.ACTIVE,
        last_message_at=now,
        message_count=2,
        token_count=10,
        created_by_id=uuid4(),
        created_at=now,
        updated_at=now,
        source_project_id=None,
    )

    conversation_result = MagicMock()
    conversation_result.scalars.return_value.first.return_value = conversation
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    thread_result = MagicMock()
    # Desired list-query shape: one row containing the thread and its bounded
    # latest-message preview.
    thread_result.all.return_value = [(thread, "Latest persisted answer")]

    db = AsyncMock()
    db.execute.side_effect = [conversation_result, count_result, thread_result]

    response = await workspace_routes.list_threads_standalone(
        conversation_id=conversation_id,
        status_filter=None,
        page=1,
        limit=50,
        db=db,
        current_user=SimpleNamespace(id=uuid4()),
    )

    assert response.threads[0].last_message_preview == "Latest persisted answer"

    list_statement = db.execute.await_args_list[2].args[0]
    compiled = str(
        list_statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "substr(chat_messages.content, 1, 240)" in compiled
    assert "chat_messages.is_deleted = false" in compiled
    assert "chat_messages.role IN ('user', 'assistant')" in compiled
    assert "ORDER BY chat_messages.created_at DESC" in compiled
