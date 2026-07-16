"""Nested v1 create_message must delegate to ChatService.create_message.

Sibling of test_v2_create_message_delegates (PR #1051): the workspace-scoped
route had the same drift — it accepted but silently discarded ``latency_ms``,
``stopped``, and ``attachment_ids``, skipped token accounting, and bypassed
the attachment org-ownership guard. These tests pin the delegation and the
route's own semantics (path thread_id is authoritative; 403 for non-editors).
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Import the actual definition module (Task 4.2 split create_message out of
# the former monolithic workspaces.py into workspace_routes/messages.py) so
# patch.object below intercepts the same _get_thread_or_404/_message_to_response
# names the handler's own globals resolve against.
from src.api.threads.workspace_routes import messages as workspaces_mod
from src.schemas.chat import ChatMessageCreate, MessageRole

pytestmark = pytest.mark.unit


def _request(thread_id=None):
    return ChatMessageCreate(
        thread_id=thread_id or uuid.uuid4(),
        content="answer text",
        role=MessageRole.ASSISTANT,
        latency_ms=1234,
        stopped=True,
        attachment_ids=[uuid.uuid4()],
    )


def _thread(can_edit=True):
    thread = MagicMock()
    thread.conversation.workspace.can_user_edit.return_value = can_edit
    return thread


def _call(request, service, thread, db=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    with (
        patch.object(
            workspaces_mod, "_get_thread_or_404", new=AsyncMock(return_value=thread)
        ),
        patch(
            "src.services.threads.chat_service.get_chat_service", return_value=service
        ),
    ):
        return asyncio.run(
            workspaces_mod.create_message(
                workspace_id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                thread_id=PATH_THREAD_ID,
                request=request,
                db=db or MagicMock(),
                current_user=user,
            )
        )


PATH_THREAD_ID = uuid.uuid4()


def test_full_request_reaches_the_service_with_path_thread_id():
    # Body carries a DIFFERENT thread_id — the path one must win, matching the
    # old inline behavior which always wrote to the path thread.
    request = _request(thread_id=uuid.uuid4())
    message = MagicMock()
    message.id = uuid.uuid4()
    service = MagicMock()
    service.create_message = AsyncMock(return_value=message)

    db = MagicMock()
    requeried = MagicMock()
    requeried.scalars.return_value.first.return_value = message
    db.execute = AsyncMock(return_value=requeried)

    with patch.object(workspaces_mod, "_message_to_response", return_value="resp"):
        resp = _call(request, service, _thread(), db)

    assert resp == "resp"
    passed_request, _user_id = service.create_message.await_args.args
    assert passed_request is request
    assert passed_request.thread_id == PATH_THREAD_ID
    assert passed_request.latency_ms == 1234
    assert passed_request.stopped is True
    assert passed_request.attachment_ids == request.attachment_ids


def test_non_editor_still_gets_403_before_delegation():
    service = MagicMock()
    service.create_message = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        _call(_request(), service, _thread(can_edit=False))
    assert exc.value.status_code == 403
    service.create_message.assert_not_awaited()


def test_service_none_maps_to_404():
    service = MagicMock()
    service.create_message = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        _call(_request(), service, _thread())
    assert exc.value.status_code == 404
