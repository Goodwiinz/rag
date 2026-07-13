from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.api.threads import workspaces as workspace_routes
from src.models.thread import ThreadStatus


@pytest.mark.asyncio
async def test_standalone_thread_list_returns_latest_message_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid4()
    thread_id = uuid4()
    now = datetime.now(timezone.utc)
    conversation = SimpleNamespace(id=conversation_id, workspace_id=uuid4())
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
    # latest-message preview. Keep the legacy scalar shape populated so this
    # fails on the missing response field rather than on mock plumbing.
    thread_result.all.return_value = [(thread, "Latest persisted answer")]
    thread_result.scalars.return_value.all.return_value = [thread]

    db = AsyncMock()
    db.execute.side_effect = [conversation_result, count_result, thread_result]
    monkeypatch.setattr(
        workspace_routes,
        "_get_workspace_or_404",
        AsyncMock(return_value=SimpleNamespace(id=conversation.workspace_id)),
    )

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
