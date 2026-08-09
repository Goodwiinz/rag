"""Regression tests for the HITL confirm-path persistence fixes.

Covers three bugs fixed in this PR:
  1. The confirm path used to call ``_persist_thread_messages``, which
     re-inserted the user row every confirm (no client_message_id → no
     dedup). It must now persist ONLY the assistant row.
  2. The resumed assistant row was never idempotent — a double-confirm
     inserted a duplicate. It must now derive a deterministic
     ``client_message_id`` from the original user row and hit the partial
     unique index.
  3. ``done`` must carry the persisted ``assistant_message_id`` in
     canonical mode so the client can reconcile its optimistic bubble.
"""

import asyncio
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.shared.enums import JobStatus


@pytest.fixture(autouse=True)
def _reset_compiled_graph_cache():
    import src.api.agent.streaming as mod

    mod._COMPILED_GRAPH = None
    yield
    mod._COMPILED_GRAPH = None


def _make_snapshot(*, user_id="user-1", plan=None):
    ai_msg = SimpleNamespace(type="ai", content="Done — confirmed action.")
    return SimpleNamespace(
        values={
            "page_context": {"type": "general"},
            "user_id": user_id,
            "messages": [ai_msg],
            "tool_executions": [],
            "retrieved_contexts": [],
            "plan": plan or [],
        },
        tasks=(),
    )


def _confirm_context(streaming_mod, agent_run_service, graph, finalize, lookup):
    return (
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
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
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ),
        patch.object(
            agent_run_service,
            "get_awaiting_confirmation_run_for_thread",
            new=lookup,
        ),
        patch.object(streaming_mod, "finalize_submission", new=finalize),
    )


@pytest.mark.asyncio
async def test_confirm_completion_finalizes_original_durable_run():
    """Resume must transition the parked AgentRun back to running, then terminal."""
    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_run_service

    snapshot = _make_snapshot()
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()
    active_run = SimpleNamespace(job_id="run-1")
    lookup = AsyncMock(return_value=active_run)
    finalize = AsyncMock()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5.6-luna",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            return_value=None,
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
            return_value=_FakeGraph(snapshot),
        ),
        patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_db),
        patch.object(
            agent_run_service,
            "get_awaiting_confirmation_run_for_thread",
            new=lookup,
            create=True,
        ),
        patch.object(streaming_mod, "finalize_submission", new=finalize),
        patch.object(
            streaming_mod._stream_buffer,
            "start_stream",
            new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ),
        patch.object(
            streaming_mod._jobs_mod,
            "_persist_assistant_message_safe",
            new=AsyncMock(return_value="assistant-msg-1"),
        ),
        patch.object(
            streaming_mod,
            "_latest_user_client_message_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        async for _ in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    lookup.assert_awaited_once_with(
        fake_db,
        thread_id=body.thread_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    statuses = [call.kwargs["status"] for call in finalize.await_args_list]
    assert statuses == [JobStatus.RUNNING, JobStatus.COMPLETED]
    assert finalize.await_args_list[-1].kwargs["run_id"] == active_run.job_id


@pytest.mark.asyncio
async def test_confirm_nested_interrupt_reparks_original_durable_run():
    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_run_service

    nested = _make_snapshot()
    nested.tasks = (
        SimpleNamespace(
            interrupts=[SimpleNamespace(value={"action": "approve_next_step"})]
        ),
    )
    graph = _SequencedGraph(_make_snapshot(), nested)
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()
    lookup = AsyncMock(return_value=SimpleNamespace(job_id="run-1"))
    finalize = AsyncMock()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5.6-luna",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    contexts = _confirm_context(
        streaming_mod, agent_run_service, graph, finalize, lookup
    )
    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(
            patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_db)
        )
        async for _ in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    statuses = [call.kwargs["status"] for call in finalize.await_args_list]
    assert statuses == [JobStatus.RUNNING, JobStatus.AWAITING_CONFIRMATION]


@pytest.mark.asyncio
async def test_confirm_failure_finalizes_original_durable_run():
    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_run_service

    graph = _FailingGraph(_make_snapshot())
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()
    lookup = AsyncMock(return_value=SimpleNamespace(job_id="run-1"))
    finalize = AsyncMock()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5.6-luna",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    contexts = _confirm_context(
        streaming_mod, agent_run_service, graph, finalize, lookup
    )
    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(
            patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_db)
        )
        async for _ in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    statuses = [call.kwargs["status"] for call in finalize.await_args_list]
    assert statuses == [JobStatus.RUNNING, JobStatus.FAILED]


@pytest.mark.asyncio
async def test_confirm_pre_resume_failure_keeps_run_parked_for_retry():
    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_run_service

    graph = _ImmediateFailingGraph(_make_snapshot())
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()
    lookup = AsyncMock(return_value=SimpleNamespace(job_id="run-1"))
    finalize = AsyncMock()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5.6-luna",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    contexts = _confirm_context(
        streaming_mod, agent_run_service, graph, finalize, lookup
    )
    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(
            patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_db)
        )
        async for _ in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    statuses = [call.kwargs["status"] for call in finalize.await_args_list]
    assert statuses == [JobStatus.RUNNING, JobStatus.AWAITING_CONFIRMATION]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("emit_event", "expected_status"),
    [
        (False, JobStatus.AWAITING_CONFIRMATION),
        (True, JobStatus.CANCELLED),
    ],
)
async def test_confirm_task_cancellation_closes_graph_and_finalizes_run(
    emit_event, expected_status
):
    from src.api.agent import streaming as streaming_mod
    from src.services.agent import agent_run_service

    graph = _CancellableGraph(_make_snapshot(), emit_event=emit_event)
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()
    lookup = AsyncMock(return_value=SimpleNamespace(job_id="run-1"))
    finalize = AsyncMock()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5.6-luna",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    async def drain():
        async for _ in streaming_mod.stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    contexts = _confirm_context(
        streaming_mod, agent_run_service, graph, finalize, lookup
    )
    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(
            patch.object(streaming_mod, "AsyncSessionLocal", return_value=fake_db)
        )
        task = asyncio.create_task(drain())
        await asyncio.wait_for(graph.waiting.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    statuses = [call.kwargs["status"] for call in finalize.await_args_list]
    assert statuses == [JobStatus.RUNNING, expected_status]
    assert graph.aclosed is True


class _FakeGraph:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.aclosed = False

    async def astream_events(self, *args, **kwargs):
        if False:  # pragma: no cover - never iterated; is_disconnected is True
            yield {}

    async def aget_state(self, config):
        return self._snapshot

    async def aclose(self):
        self.aclosed = True


class _SequencedGraph(_FakeGraph):
    def __init__(self, *snapshots):
        super().__init__(snapshots[-1])
        self._snapshots = iter(snapshots)

    async def aget_state(self, config):
        return next(self._snapshots)


class _FailingGraph(_FakeGraph):
    async def astream_events(self, *args, **kwargs):
        yield {"event": "on_chat_model_stream", "data": {}}
        raise RuntimeError("resume failed")


class _ImmediateFailingGraph(_FakeGraph):
    async def astream_events(self, *args, **kwargs):
        raise RuntimeError("resume failed before first event")
        yield  # pragma: no cover


class _CancellableGraph(_FakeGraph):
    def __init__(self, snapshot, *, emit_event):
        super().__init__(snapshot)
        self.emit_event = emit_event
        self.emitted = False
        self.waiting = asyncio.Event()

    def astream_events(self, *args, **kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.emit_event and not self.emitted:
            self.emitted = True
            return {"event": "on_chat_model_stream", "data": {}}
        self.waiting.set()
        await asyncio.Event().wait()
        raise StopAsyncIteration  # pragma: no cover

    async def aclose(self):
        self.aclosed = True


@pytest.mark.asyncio
async def test_confirm_persists_only_assistant_row_not_user_row():
    """The user row was already persisted by the original /stream request;
    the confirm path must not re-insert it."""
    from src.api.agent.streaming import stream_confirm_event_generator

    snapshot = _make_snapshot()
    persist_mock = AsyncMock(return_value="assistant-msg-1")
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()

    # Connected client — the confirm loop now routes events through
    # _graph_events_with_keepalive, which checks is_disconnected() before
    # pulling each event. A True here would (correctly) trigger the
    # cancel/persist-partial branch instead of a normal completion.
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=lambda: None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.checkpointer.reset_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=_FakeGraph(snapshot),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=fake_db,
        ),
        patch(
            "src.services.agent.agent_execution_service._persist_assistant_message_safe",
            new=persist_mock,
        ),
        patch(
            "src.api.agent.streaming._latest_user_client_message_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        async for _ in stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    persist_mock.assert_awaited_once()
    kwargs = persist_mock.await_args.kwargs
    # Must NOT have hit the user-row path at all — only the assistant row.
    assert persist_mock.await_count == 1
    # The role is implicit (always assistant inside _persist_assistant_message),
    # but the call must carry the resumed turn's content + plan + token_usage.
    assert kwargs["thread_id"] == body.thread_id
    assert kwargs["content"] == "Done — confirmed action."
    assert kwargs["model_name"] == "gpt-5"
    assert kwargs["plan"] == [] or kwargs["plan"] is None


@pytest.mark.asyncio
async def test_confirm_derives_idempotent_assistant_cmid_from_user_row():
    """A double-confirm must hit the assistant partial unique index. The
    resumed turn has no fresh cmid, so the assistant key is derived (uuid5)
    from the original user row's client_message_id."""
    from src.api.agent.streaming import stream_confirm_event_generator

    import uuid as _uuid

    user_cmid = "22222222-2222-2222-2222-222222222222"
    expected_assistant_cmid = str(
        _uuid.uuid5(_uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}")
    )

    snapshot = _make_snapshot()
    persist_mock = AsyncMock(return_value="assistant-msg-1")
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()

    # Connected client — the confirm loop now routes events through
    # _graph_events_with_keepalive, which checks is_disconnected() before
    # pulling each event. A True here would (correctly) trigger the
    # cancel/persist-partial branch instead of a normal completion.
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=lambda: None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.checkpointer.reset_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=_FakeGraph(snapshot),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=fake_db,
        ),
        patch(
            "src.services.agent.agent_execution_service._persist_assistant_message_safe",
            new=persist_mock,
        ),
        patch(
            "src.api.agent.streaming._latest_user_client_message_id",
            new=AsyncMock(return_value=user_cmid),
        ),
    ):
        async for _ in stream_confirm_event_generator(
            body, request, current_user
        ):
            pass

    kwargs = persist_mock.await_args.kwargs
    assert kwargs["client_message_id"] == expected_assistant_cmid


@pytest.mark.asyncio
async def test_confirm_done_carries_assistant_message_id_in_canonical_mode():
    """In canonical mode the done event must carry assistant_message_id so
    the client can reconcile its optimistic bubble (legacy mode omits it)."""
    from src.api.agent.streaming import stream_confirm_event_generator

    snapshot = _make_snapshot(
        plan=[{"step": 1, "description": "Ingest", "tool": "ingest_arxiv"}]
    )
    fake_db = AsyncMock()
    fake_db.close = AsyncMock()

    # Connected client — the confirm loop now routes events through
    # _graph_events_with_keepalive, which checks is_disconnected() before
    # pulling each event. A True here would (correctly) trigger the
    # cancel/persist-partial branch instead of a normal completion.
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="gpt-5",
    )
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=lambda: None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.checkpointer.reset_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            return_value=_FakeGraph(snapshot),
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=fake_db,
        ),
        patch(
            "src.services.agent.agent_execution_service._persist_assistant_message_safe",
            new=AsyncMock(return_value="assistant-msg-1"),
        ),
        patch(
            "src.api.agent.streaming._latest_user_client_message_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.streaming._canonical_persistence_enabled",
            return_value=True,
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    done_events = [e for e in events if "event: done" in e]
    assert len(done_events) == 1
    assert "assistant_message_id" in done_events[0]
    assert "assistant-msg-1" in done_events[0]
