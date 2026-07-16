"""Message-feedback endpoints must require edit rights, not just read access.

Regression guard for the Hunt-5 finding: update_message_feedback and
update_message_standalone mutated feedback after only a read-level access
check (member/public viewer), unlike every other mutator in workspaces.py.
A viewer — or any authenticated user on a public workspace — could write
another user's message feedback. Mocked DB, no real Postgres.

Task 4.3 moved the message-feedback persistence into
``src/services/threads/message_service.py``, which fetches the message via
the shared ``workspace_access.get_message`` funnel — these tests patch that
one seam instead of the pre-4.3 router-inline ``_get_thread_or_404``/
``_get_workspace_or_404`` + raw ``db.execute`` chain.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

GET_MESSAGE = "src.services.threads.workspace_access.get_message"


def _message_with_edit_permission(can_edit: bool) -> SimpleNamespace:
    workspace = MagicMock()
    workspace.can_user_edit.return_value = can_edit
    return SimpleNamespace(
        thread=SimpleNamespace(conversation=SimpleNamespace(workspace=workspace)),
        feedback_rating=None,
        feedback_text=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_message_feedback_forbids_non_editor() -> None:
    from src.api.threads.workspaces import update_message_feedback
    from src.schemas.chat import ChatMessageUpdate

    user_id = uuid4()
    message = _message_with_edit_permission(can_edit=False)

    db = AsyncMock()
    db.commit = AsyncMock()

    with patch(GET_MESSAGE, new=AsyncMock(return_value=message)):
        with pytest.raises(HTTPException) as exc_info:
            await update_message_feedback(
                workspace_id=uuid4(),
                conversation_id=uuid4(),
                thread_id=uuid4(),
                message_id=uuid4(),
                request=ChatMessageUpdate(feedback_rating=5),
                db=db,
                current_user=SimpleNamespace(id=user_id),
            )

    assert exc_info.value.status_code == 403
    message.thread.conversation.workspace.can_user_edit.assert_called_once_with(
        str(user_id)
    )
    db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_service_feedback_requires_edit_rights() -> None:
    """The service-layer path (threads.py PATCH -> chat_service) must also
    require edit rights, not just the read access get_message grants."""
    from src.schemas.chat import ChatMessageUpdate
    from src.services.threads.chat_service import ChatService

    user_id = uuid4()
    message = _message_with_edit_permission(can_edit=False)

    db = AsyncMock()
    db.commit = AsyncMock()
    service = ChatService(db)

    with patch(GET_MESSAGE, new=AsyncMock(return_value=message)):
        result = await service.update_message_feedback(
            uuid4(), ChatMessageUpdate(feedback_rating=5), user_id
        )

    assert result is None  # -> 404 at the endpoint
    message.thread.conversation.workspace.can_user_edit.assert_called_once_with(
        str(user_id)
    )
    db.commit.assert_not_called()
    assert message.feedback_rating is None  # not mutated


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_message_standalone_forbids_non_editor() -> None:
    from src.api.threads.workspaces import update_message_standalone
    from src.schemas.chat import ChatMessageUpdate

    user_id = uuid4()
    message = _message_with_edit_permission(can_edit=False)

    db = AsyncMock()
    db.commit = AsyncMock()

    with patch(GET_MESSAGE, new=AsyncMock(return_value=message)):
        with pytest.raises(HTTPException) as exc_info:
            await update_message_standalone(
                message_id=uuid4(),
                request=ChatMessageUpdate(feedback_rating=5),
                db=db,
                current_user=SimpleNamespace(id=user_id),
            )

    assert exc_info.value.status_code == 403
    message.thread.conversation.workspace.can_user_edit.assert_called_once_with(
        str(user_id)
    )
    db.commit.assert_not_called()
