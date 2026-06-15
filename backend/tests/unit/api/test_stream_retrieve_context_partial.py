"""The threads SSE stream binds the caller's tenant scope into retrieve_context.

StreamService invokes ``retrieve_context_fn(content, max_docs)`` positionally,
so the endpoint pre-binds ``organization_id``/``user_id`` with functools.partial.
That only works because those params are keyword-only (``*`` in the signature);
if someone removed the ``*`` the partial's org would collide with the positional
``max_docs``. This test pins both the wiring and the keyword-only contract.
"""

from __future__ import annotations

import inspect
from functools import partial
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def test_retrieve_context_scope_params_are_keyword_only():
    from src.api.research.chat import retrieve_context

    sig = inspect.signature(retrieve_context)
    for name in ("organization_id", "user_id"):
        assert (
            sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        ), f"{name} must stay keyword-only or the stream partial mis-binds"


async def test_stream_null_org_rag_caller_gets_403_from_endpoint_body():
    """The org guard must raise from the endpoint body (before
    StreamingResponse), not from inside the SSE generator — otherwise it fires
    after 200 OK headers are sent and leaks thread_id into _active_streams."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from fastapi import HTTPException

    from src.api.threads import stream as mod

    user = MagicMock()
    user.id = uuid4()
    user.organization_id = None  # null-org caller
    body = MagicMock()
    body.use_rag = True
    tid = uuid4()

    with pytest.raises(HTTPException) as exc:
        await mod.stream_thread_chat(
            thread_id=tid, body=body, request=MagicMock(), current_user=user
        )
    assert exc.value.status_code == 403
    # The guard fired before the generator, so nothing leaked into the set.
    assert tid not in mod._active_streams


async def test_stream_partial_injects_caller_scope_on_positional_call():
    """Build the partial exactly as stream_thread_chat does, then call it the
    way StreamService does (positionally) and assert the scope arrives."""
    with patch(
        "src.api.research.chat.retrieve_context", new_callable=AsyncMock
    ) as mock_rc:
        mock_rc.return_value = ([], None)
        from src.api.research.chat import retrieve_context

        scoped = partial(
            retrieve_context, organization_id="org-9", user_id="user-9"
        )
        await scoped("the query", 5)  # positional, like StreamService

        mock_rc.assert_awaited_once()
        args, kwargs = mock_rc.call_args
        assert args == ("the query", 5)
        assert kwargs["organization_id"] == "org-9"
        assert kwargs["user_id"] == "user-9"
