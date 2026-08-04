"""The real graph invocation receives bounded correlation-only metadata."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.agent_submission_service import AcceptedSubmission
from src.services.agent.runtime_snapshot import empty_runtime_snapshot
from tests.utils.agent_stream import make_stream_request

USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ORG_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
THREAD_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CLIENT_MESSAGE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
RUN_ID = "55555555-5555-5555-5555-555555555555"
USER_MESSAGE_ID = "66666666-6666-6666-6666-666666666666"
REQUEST_ID = "request-trace-123"
PROMPT = "synthetic prompt content that must not enter trace metadata"


class _CapturingGraph:
    def __init__(self) -> None:
        self.config: dict[str, Any] | None = None

    async def astream_events(
        self, *_args: Any, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        self.config = kwargs["config"]
        if False:
            yield {}

    async def aget_state(self, _config: Any) -> Any:
        return SimpleNamespace(values={"messages": []}, tasks=())


async def _capture_stream_metadata(*, durable: bool) -> dict[str, str]:
    from src.api.agent import streaming as streaming_mod

    graph = _CapturingGraph()
    body = make_stream_request(
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "client_message_id": str(CLIENT_MESSAGE_ID),
            }
        ],
        thread_id=str(THREAD_ID) if durable else "",
    )
    request = SimpleNamespace(
        state=SimpleNamespace(request_id=REQUEST_ID),
        is_disconnected=AsyncMock(return_value=False),
    )
    current_user = SimpleNamespace(id=USER_ID, organization_id=ORG_ID)
    accepted = AcceptedSubmission(
        run_id=RUN_ID,
        thread_id=str(THREAD_ID),
        user_message_id=USER_MESSAGE_ID,
        outbox_id="outbox-1",
        idempotency_key="key-1",
    )
    thread_obj = SimpleNamespace(id=THREAD_ID)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=AsyncMock()),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(
                return_value=(thread_obj, "conversation-1") if durable else (None, None)
            ),
        ),
        patch.object(
            streaming_mod,
            "accept_submission",
            new=AsyncMock(return_value=accepted),
        ),
        patch.object(
            streaming_mod,
            "mark_submission_dispatched",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_finalize_run",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(side_effect=RuntimeError("redis down")),
        ),
        patch(
            "src.services.agent.observability.configure_langsmith", return_value=None
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=graph,
        ),
        patch(
            "src.services.agent.fast_path.classify_fast_path_turn",
            return_value=SimpleNamespace(eligible=False),
        ),
        patch(
            "src.services.agent.runtime_snapshot.create_runtime_snapshot",
            new=AsyncMock(return_value=empty_runtime_snapshot()),
        ),
        patch.object(
            streaming_mod._jobs_mod,
            "_persist_assistant_message_safe",
            new=AsyncMock(return_value="assistant-1"),
        ),
    ):
        async for _frame in streaming_mod.stream_event_generator(
            body, request, current_user
        ):
            pass

    assert graph.config is not None
    return graph.config["metadata"]


@asynccontextmanager
async def _session_context(db: Any) -> AsyncIterator[Any]:
    yield db


@pytest.mark.asyncio
async def test_stream_graph_config_correlates_trace_to_release_and_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA", "deployment-sha-123")
    monkeypatch.setenv("IMAGE_TAG", "backend-image-456")

    metadata = await _capture_stream_metadata(durable=True)

    assert metadata == {
        "user_id": str(USER_ID),
        "org_id": str(ORG_ID),
        "thread_id": str(THREAD_ID),
        "request_id": REQUEST_ID,
        "agent_run_id": RUN_ID,
        "user_message_id": USER_MESSAGE_ID,
        "client_message_id": str(CLIENT_MESSAGE_ID),
        "deployment_sha": "deployment-sha-123",
        "image_tag": "backend-image-456",
    }
    assert PROMPT not in str(metadata)


@pytest.mark.asyncio
async def test_stream_graph_config_degrades_without_durable_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA", "deployment-sha-123")
    monkeypatch.setenv("IMAGE_TAG", "backend-image-456")

    metadata = await _capture_stream_metadata(durable=False)

    assert metadata == {
        "user_id": str(USER_ID),
        "org_id": str(ORG_ID),
        "request_id": REQUEST_ID,
        "client_message_id": str(CLIENT_MESSAGE_ID),
        "deployment_sha": "deployment-sha-123",
        "image_tag": "backend-image-456",
    }
    assert (
        not {
            "thread_id",
            "agent_run_id",
            "user_message_id",
        }
        & metadata.keys()
    )


@pytest.mark.asyncio
async def test_background_graph_config_uses_same_correlation_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services.agent import agent_execution_service as execution_mod

    monkeypatch.setenv("GIT_SHA", "deployment-sha-123")
    monkeypatch.setenv("IMAGE_TAG", "backend-image-456")
    job_id = "77777777-7777-7777-7777-777777777777"
    body = make_stream_request(
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "client_message_id": str(CLIENT_MESSAGE_ID),
            }
        ],
        thread_id=None,
    )
    current_user = SimpleNamespace(id=USER_ID, organization_id=ORG_ID)
    graph = MagicMock()
    graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
    graph.aget_state = AsyncMock(return_value=None)
    db = AsyncMock()

    with (
        patch.object(
            execution_mod,
            "AsyncSessionLocal",
            return_value=_session_context(db),
        ),
        patch.object(
            execution_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(None, None)),
        ),
        patch.object(
            execution_mod,
            "_resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=graph,
        ),
        patch(
            "src.services.agent.runtime_snapshot.create_runtime_snapshot",
            new=AsyncMock(return_value=empty_runtime_snapshot()),
        ),
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
        ),
        patch.object(
            execution_mod,
            "_set_job_async",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await execution_mod._run_agent_graph(job_id, body, current_user)

    metadata = graph.ainvoke.await_args.kwargs["config"]["metadata"]
    assert metadata == {
        "user_id": str(USER_ID),
        "org_id": str(ORG_ID),
        "thread_id": job_id,
        "agent_run_id": job_id,
        "client_message_id": str(CLIENT_MESSAGE_ID),
        "deployment_sha": "deployment-sha-123",
        "image_tag": "backend-image-456",
    }
    assert PROMPT not in str(metadata)
