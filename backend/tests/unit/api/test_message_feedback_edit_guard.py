"""Message-feedback endpoints must require edit rights, not just read access.

Regression guard for the Hunt-5 finding: update_message_feedback and
update_message_standalone mutated feedback after only a read-level access
check (member/public viewer), unlike every other mutator in workspaces.py.
A viewer — or any authenticated user on a public workspace — could write
another user's message feedback. Mocked DB, no real Postgres.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

# Patch target is where update_message_feedback/update_message_standalone are
# actually defined (Task 4.2 split them out of the former monolithic
# workspaces.py) — mock.patch needs the module whose globals the handlers'
# name lookups resolve against, not the backward-compat re-export path used
# by the `import` statements below.
MODULE = "src.api.threads.workspace_routes.messages"


def _execute_returning(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_message_feedback_forbids_non_editor() -> None:
    from src.api.threads.workspaces import update_message_feedback
    from src.schemas.chat import ChatMessageUpdate

    user_id = uuid4()
    workspace = MagicMock()
    workspace.can_user_edit.return_value = False
    thread = SimpleNamespace(conversation=SimpleNamespace(workspace=workspace))

    db = AsyncMock()
    db.commit = AsyncMock()

    with patch(f"{MODULE}._get_thread_or_404", new=AsyncMock(return_value=thread)):
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
    workspace.can_user_edit.assert_called_once_with(str(user_id))
    db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chat_service_feedback_requires_edit_rights() -> None:
    """The service-layer path (threads.py PATCH -> chat_service) must also
    require edit rights, not just the read access get_message grants."""
    from src.schemas.chat import ChatMessageUpdate
    from src.services.threads.chat_service import ChatService

    user_id = uuid4()
    workspace = MagicMock()
    workspace.can_user_edit.return_value = False
    message = SimpleNamespace(
        thread=SimpleNamespace(conversation=SimpleNamespace(workspace=workspace)),
        feedback_rating=None,
        feedback_text=None,
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    service = ChatService(db)
    service.get_message = AsyncMock(return_value=message)

    result = await service.update_message_feedback(
        uuid4(), ChatMessageUpdate(feedback_rating=5), user_id
    )

    assert result is None  # -> 404 at the endpoint
    workspace.can_user_edit.assert_called_once_with(str(user_id))
    db.commit.assert_not_called()
    assert message.feedback_rating is None  # not mutated


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_message_standalone_forbids_non_editor() -> None:
    from src.api.threads.workspaces import update_message_standalone
    from src.schemas.chat import ChatMessageUpdate

    user_id = uuid4()
    message = SimpleNamespace(thread_id=uuid4())
    thread = SimpleNamespace(conversation_id=uuid4())
    conversation = SimpleNamespace(workspace_id=uuid4())

    db = AsyncMock()
    # message lookup -> thread lookup -> conversation lookup
    db.execute = AsyncMock(
        side_effect=[
            _execute_returning(message),
            _execute_returning(thread),
            _execute_returning(conversation),
        ]
    )
    db.commit = AsyncMock()

    workspace = MagicMock()
    workspace.can_user_edit.return_value = False

    with patch(
        f"{MODULE}._get_workspace_or_404", new=AsyncMock(return_value=workspace)
    ):
        with pytest.raises(HTTPException) as exc_info:
            await update_message_standalone(
                message_id=uuid4(),
                request=ChatMessageUpdate(feedback_rating=5),
                db=db,
                current_user=SimpleNamespace(id=user_id),
            )

    assert exc_info.value.status_code == 403
    workspace.can_user_edit.assert_called_once_with(str(user_id))
    db.commit.assert_not_called()
