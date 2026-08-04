from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessageChunk

pytestmark = pytest.mark.integration


class _FakeLuna:
    async def astream(self, _messages, *, config=None):
        yield AIMessageChunk(content="hel")
        yield AIMessageChunk(
            content="lo",
            usage_metadata={
                "input_tokens": 12,
                "output_tokens": 2,
                "total_tokens": 14,
            },
        )


class _NoGraphExecution:
    def __init__(self):
        self.astream_called = False
        self.aupdate_state = AsyncMock(return_value=None)

    async def astream_events(self, *_args, **_kwargs):
        self.astream_called = True
        raise AssertionError("eligible fast-path turn entered LangGraph execution")
        yield  # pragma: no cover


class _FailingLuna:
    async def astream(self, _messages, *, config=None):
        yield AIMessageChunk(content="partial")
        raise RuntimeError("model stream broke")


class _CancelledLuna:
    async def astream(self, _messages, *, config=None):
        yield AIMessageChunk(content="partial")
        raise asyncio.CancelledError()


async def test_fast_chunks_wait_for_user_persistence_before_release():
    from src.services.agent.fast_path import stream_fast_path_chunks

    model_started = asyncio.Event()
    allow_persist = asyncio.Event()

    class ImmediateModel:
        async def astream(self, _messages, *, config=None):
            model_started.set()
            yield AIMessageChunk(content="first")

    async def persist_user():
        await allow_persist.wait()

    chunks = stream_fast_path_chunks(
        llm=ImmediateModel(),
        messages=[],
        persist_user=persist_user,
    )
    first = asyncio.create_task(anext(chunks))

    await asyncio.wait_for(model_started.wait(), timeout=1)
    await asyncio.sleep(0)
    assert first.done() is False

    allow_persist.set()
    assert (await asyncio.wait_for(first, timeout=1)).content == "first"


async def test_eligible_turn_streams_luna_and_reconciles_checkpoint_before_done(
    monkeypatch,
):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    thread = SimpleNamespace(id=uuid4(), conversation_id=uuid4())
    user_cmid = uuid4()

    from src.api.agent import streaming as streaming_mod
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage
    from src.core.config import get_settings
    from src.services.agent import agent_execution_service as jobs_mod
    from src.services.agent import llm_factory

    body = AgentExecuteRequest(
        messages=[
            AgentMessage(
                role="user",
                content="Explain why the sky appears blue",
                client_message_id=user_cmid,
            )
        ],
        page_context={"type": "chat"},
        use_rag=False,
        thread_id=str(thread.id),
    )
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))

    settings = get_settings()
    monkeypatch.setattr(settings, "AGENT_FAST_PATH_ENABLED", True)
    monkeypatch.setattr(settings, "AGENT_FAST_PATH_MAX_INPUT_CHARS", 8_000)
    monkeypatch.setattr(llm_factory, "build_fast_path_llm", lambda: _FakeLuna())
    monkeypatch.setenv("AGENT_CANONICAL_PERSISTENCE", "true")

    fake_graph = _NoGraphExecution()
    fake_session = SimpleNamespace(close=AsyncMock())
    persist_user = AsyncMock(return_value=True)
    persist_assistant = AsyncMock(return_value="assistant-row-id")

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_session),
        patch.object(streaming_mod, "_accept_eligible", return_value=False),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(thread, str(thread.conversation_id))),
        ),
        patch.object(
            streaming_mod,
            "_persist_user_message_guarded",
            new=persist_user,
        ),
        patch.object(
            jobs_mod,
            "_persist_assistant_message_safe",
            new=persist_assistant,
        ),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
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
            new=lambda **_kwargs: fake_graph,
        ),
    ):
        events = [
            event
            async for event in streaming_mod.stream_event_generator(body, request, user)
        ]

    assert fake_graph.astream_called is False
    persist_user.assert_awaited_once()
    token_frames = [event for event in events if "event: token" in event]
    assert '"content": "hel"' in token_frames[0]
    assert '"content": "lo"' in token_frames[1]

    update_args = fake_graph.aupdate_state.await_args.args
    checkpoint_messages = update_args[1]["messages"]
    assert [message.content for message in checkpoint_messages] == [
        "Explain why the sky appears blue",
        "hello",
    ]
    assert checkpoint_messages[0].id == str(user_cmid)
    assert checkpoint_messages[1].id

    done_index = next(i for i, event in enumerate(events) if "event: done" in event)
    assert fake_graph.aupdate_state.await_count == 1
    assert done_index == len(events) - 1
    persist_kwargs = persist_assistant.await_args.kwargs
    assert persist_kwargs["content"] == "hello"
    assert persist_kwargs["model_name"] == "gpt-5.6-luna"
    fake_session.close.assert_awaited_once()


async def test_ineligible_turn_keeps_langgraph_path(
    monkeypatch,
):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    thread = SimpleNamespace(id=uuid4(), conversation_id=uuid4(), source_project=None)

    from src.api.agent import streaming as streaming_mod
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage
    from src.core.config import get_settings
    from src.services.agent import agent_execution_service as jobs_mod

    body = AgentExecuteRequest(
        messages=[AgentMessage(role="user", content="Search my documents")],
        page_context={"type": "documents"},
        use_rag=True,
        thread_id=str(thread.id),
    )
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    settings = get_settings()
    monkeypatch.setattr(settings, "AGENT_FAST_PATH_ENABLED", True)

    class GraphPath:
        def __init__(self):
            self.astream_called = False
            self._snapshot = SimpleNamespace(values={"messages": []}, tasks=())

        async def astream_events(self, *_args, **_kwargs):
            self.astream_called = True
            if False:
                yield

        async def aget_state(self, _config):
            return self._snapshot

    graph = GraphPath()
    fake_session = SimpleNamespace(close=AsyncMock())
    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_session),
        patch.object(streaming_mod, "_accept_eligible", return_value=False),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(thread, str(thread.conversation_id))),
        ),
        patch.object(
            streaming_mod,
            "_persist_user_message_guarded",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            jobs_mod,
            "_persist_assistant_message_safe",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_resolve_and_bind_project",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod,
            "_clear_stale_pending_confirmation",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.observability.configure_langsmith",
            new=lambda: None,
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
            new=lambda **_kwargs: graph,
        ),
        patch(
            "src.services.agent.runtime_snapshot.create_runtime_snapshot",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    id="",
                    tool_registry_hash="",
                    tool_registry_version="",
                    tool_metadata={},
                    project_skill_catalog=[],
                    loaded_skill_versions=[],
                )
            ),
        ),
    ):
        _events = [
            event
            async for event in streaming_mod.stream_event_generator(body, request, user)
        ]

    assert graph.astream_called is True


@pytest.mark.parametrize(
    ("model", "cancelled"),
    [(_FailingLuna(), False), (_CancelledLuna(), True)],
)
async def test_luna_failure_persists_streamed_partial_as_stopped(
    monkeypatch, model, cancelled
):
    user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    thread = SimpleNamespace(id=uuid4(), conversation_id=uuid4())
    user_cmid = uuid4()

    from src.api.agent import streaming as streaming_mod
    from src.api.agent.execute import AgentExecuteRequest, AgentMessage
    from src.core.config import get_settings
    from src.services.agent import agent_execution_service as jobs_mod
    from src.services.agent import llm_factory

    body = AgentExecuteRequest(
        messages=[
            AgentMessage(
                role="user",
                content="Explain why rainbows form",
                client_message_id=user_cmid,
            )
        ],
        page_context={"type": "chat"},
        use_rag=False,
        thread_id=str(thread.id),
    )
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    settings = get_settings()
    monkeypatch.setattr(settings, "AGENT_FAST_PATH_ENABLED", True)
    monkeypatch.setattr(settings, "AGENT_FAST_PATH_MAX_INPUT_CHARS", 8_000)
    monkeypatch.setattr(llm_factory, "build_fast_path_llm", lambda: model)

    fake_session = SimpleNamespace(close=AsyncMock())
    persist_assistant = AsyncMock(return_value="partial-row-id")
    with (
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_session),
        patch.object(streaming_mod, "_accept_eligible", return_value=False),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(thread, str(thread.conversation_id))),
        ),
        patch.object(
            streaming_mod,
            "_persist_user_message_guarded",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            jobs_mod,
            "_persist_assistant_message_safe",
            new=persist_assistant,
        ),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(return_value=None),
        ),
    ):
        events = []
        if cancelled:
            with pytest.raises(asyncio.CancelledError):
                async for event in streaming_mod.stream_event_generator(
                    body, request, user
                ):
                    events.append(event)
        else:
            events = [
                event
                async for event in streaming_mod.stream_event_generator(
                    body, request, user
                )
            ]

    assert any("event: token" in event for event in events)
    assert any("event: error" in event for event in events) is (not cancelled)
    persist_assistant.assert_awaited_once()
    assert persist_assistant.await_args.kwargs["content"] == "partial"
    assert persist_assistant.await_args.kwargs["stopped"] is True
