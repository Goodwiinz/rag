"""Tests for the confirm flow retry logic when checkpoint is not found on first attempt."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_compiled_graph_cache():
    """Clear cached compiled graph between tests to avoid cross-test leakage."""
    import src.api.agent.streaming as mod

    mod._COMPILED_GRAPH = None
    yield
    mod._COMPILED_GRAPH = None


class _FakeGraphWithRetry:
    """Graph that returns None on first aget_state call, then succeeds."""

    def __init__(self, snapshot):
        self._snapshot = snapshot
        self._call_count = 0

    async def astream_events(self, *args, **kwargs):
        if False:
            yield {}

    async def aget_state(self, config):
        self._call_count += 1
        if self._call_count == 1:
            return SimpleNamespace(values={}, tasks=())
        return self._snapshot


class _FakeGraphNotFound:
    """Graph that always returns empty state (thread never found)."""

    async def astream_events(self, *args, **kwargs):
        if False:
            yield {}

    async def aget_state(self, config):
        return SimpleNamespace(values={}, tasks=())


@pytest.mark.asyncio
async def test_confirm_retries_on_first_aget_state_miss():
    """When aget_state returns empty on first call, the confirm flow should
    reset the checkpointer and retry. If the second attempt succeeds, the
    stream should complete normally (not return 'Thread not found')."""
    from src.api.agent.streaming import stream_confirm_event_generator

    snapshot = SimpleNamespace(
        values={
            "page_context": {"type": "general"},
            "user_id": "user-1",
            "messages": [],
            "tool_executions": [],
        },
        tasks=(),
    )

    call_count = {"get_checkpointer": 0, "compile": 0}

    async def fake_get_checkpointer():
        call_count["get_checkpointer"] += 1
        return object()

    graph_instances = []

    def fake_compile(*, checkpointer, store=None):
        call_count["compile"] += 1
        if call_count["compile"] == 1:
            g = _FakeGraphWithRetry(snapshot)
        else:
            g = _FakeGraphWithRetry(snapshot)
            g._call_count = 1  # Skip the "miss" on retry
        graph_instances.append(g)
        return g

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-abc", confirmed=True, model="")
    current_user = Mock(id="user-1", organization_id="org-1")

    with (
        patch(
            "src.services.agent.observability.configure_langsmith",
            side_effect=lambda: None,
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=fake_get_checkpointer,
        ),
        patch(
            "src.services.agent.checkpointer.reset_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            side_effect=fake_compile,
        ),
        patch(
            "src.api.agent.streaming._persist_thread_messages",
            new=AsyncMock(return_value=None),
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    # Should have called get_checkpointer twice (initial + retry)
    assert call_count["get_checkpointer"] == 2
    # Should NOT contain "Thread not found"
    error_events = [e for e in events if "Thread not found" in e]
    assert len(error_events) == 0
    # Should have a done event
    done_events = [e for e in events if "done" in e]
    assert len(done_events) > 0


@pytest.mark.asyncio
async def test_confirm_returns_thread_not_found_after_both_attempts_fail():
    """If both aget_state attempts return empty, emit 'Thread not found'."""
    from src.api.agent.streaming import stream_confirm_event_generator

    def fake_compile(*, checkpointer, store=None):
        return _FakeGraphNotFound()

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(thread_id="thread-gone", confirmed=True, model="")
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
            "src.services.agent.graph.compile_agent_graph",
            side_effect=fake_compile,
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    # Should contain "Thread not found" error
    error_events = [e for e in events if "Thread not found" in e]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_confirm_rejects_legacy_checkpoint_without_owned_thread():
    """A checkpoint without user_id must not be resumable by a different user."""
    from src.api.agent.streaming import stream_confirm_event_generator

    class _FakeGraphLegacyCheckpoint:
        def __init__(self):
            self.stream_started = False

        async def astream_events(self, *args, **kwargs):
            self.stream_started = True
            if False:
                yield {}

        async def aget_state(self, config):
            return SimpleNamespace(
                values={
                    "page_context": {"type": "general"},
                    "pending_confirmation": {
                        "tools": [{"name": "ingest_arxiv_papers", "args": {}}]
                    },
                    "messages": [],
                    "tool_executions": [],
                },
                tasks=(),
            )

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value=None))
    )
    fake_db.close = AsyncMock()

    fake_graph = _FakeGraphLegacyCheckpoint()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    body = SimpleNamespace(
        thread_id="11111111-1111-1111-1111-111111111111",
        confirmed=True,
        model="",
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
            "src.services.agent.graph.compile_agent_graph",
            return_value=fake_graph,
        ),
        patch(
            "src.api.agent.streaming.AsyncSessionLocal",
            return_value=fake_db,
        ),
    ):
        events = []
        async for event in stream_confirm_event_generator(
            body, request, current_user
        ):
            events.append(event)

    error_events = [e for e in events if "Thread not found" in e]
    assert len(error_events) == 1
    assert fake_graph.stream_started is False
