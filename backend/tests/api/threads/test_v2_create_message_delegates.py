"""POST /api/v2/messages must delegate to ChatService.create_message.

The standalone v2 route used to reimplement message creation and drifted from
the canonical service: it accepted but silently discarded ``latency_ms``,
``stopped``, and ``attachment_ids`` (legacy-mode clients lost the stopped badge
and response time on reload), skipped token accounting, and bypassed the
attachment org-ownership guard. Delegating to the service closes all of that
at once; these tests pin the delegation so the drift can't come back.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Import the actual definition module (Task 4.2 split create_message_standalone
# out of the former monolithic workspaces.py into workspace_routes/messages.py)
# so patch.object below intercepts the same _message_to_response name the
# handler's own globals resolve against.
from src.api.threads.workspace_routes import messages as workspaces_mod
from src.schemas.chat import ChatMessageCreate, MessageRole

pytestmark = pytest.mark.unit


def _request():
    return ChatMessageCreate(
        thread_id=uuid.uuid4(),
        content="answer text",
        role=MessageRole.ASSISTANT,
        latency_ms=1234,
        stopped=True,
        attachment_ids=[uuid.uuid4()],
    )


def _call(request, service, db=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    with patch(
        "src.services.threads.chat_service.get_chat_service", return_value=service
    ):
        return asyncio.run(
            workspaces_mod.create_message_standalone(
                request=request, db=db or MagicMock(), current_user=user
            )
        )


def test_full_request_reaches_the_service():
    request = _request()
    message = MagicMock()
    message.id = uuid.uuid4()
    service = MagicMock()
    service.create_message = AsyncMock(return_value=message)

    db = MagicMock()
    requeried = MagicMock()
    requeried.scalars.return_value.first.return_value = message
    db.execute = AsyncMock(return_value=requeried)

    with patch.object(workspaces_mod, "_message_to_response", return_value="resp"):
        resp = _call(request, service, db)

    assert resp == "resp"
    # The whole ChatMessageCreate — latency_ms, stopped, attachment_ids — must
    # reach the canonical service, not a partial re-build of it.
    passed_request, _user_id = service.create_message.await_args.args
    assert passed_request is request
    assert passed_request.latency_ms == 1234
    assert passed_request.stopped is True
    assert passed_request.attachment_ids == request.attachment_ids


def test_service_none_maps_to_404():
    service = MagicMock()
    service.create_message = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        _call(_request(), service)
    assert exc.value.status_code == 404
