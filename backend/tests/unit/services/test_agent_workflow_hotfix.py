"""Regression tests for the 8 agent workflow bugs ported from develop (PR #383 hotfix)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from langgraph.errors import GraphInterrupt

pytestmark = pytest.mark.asyncio


def _make_user():
    user = Mock()
    user.id = uuid4()
    return user


@asynccontextmanager
async def _session_cm(db):
    yield db


class TestThreadOwnership:
    """Bug 1 — thread lookup must enforce workspace ownership."""

    async def test_foreign_thread_id_is_not_resolved(self):
        from src.api.agent.execute import AgentExecuteRequest
        from src.api.agent.jobs import _persist_thread_messages

        user = _make_user()
        foreign_thread_id = str(uuid4())
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=Mock(return_value=None))
        )
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        request = AgentExecuteRequest(
            messages=[{"role": "user", "content": "hello"}],
            thread_id=foreign_thread_id,
        )

        thread_id, conversation_id = await _persist_thread_messages(
            db, user, request, "assistant reply", None
        )

        assert thread_id == foreign_thread_id or thread_id == ""
        assert conversation_id == ""
        db.commit.assert_not_called()


class TestStreamingGraphInterrupt:
    """Bug 2 — GraphInterrupt handler must not KeyError on empty config."""

    async def test_graph_interrupt_before_config_populated_emits_confirmation(self):
        from src.api.agent.execute import AgentExecuteRequest
        from src.api.agent.streaming import stream_event_generator

        request_body = AgentExecuteRequest(
            messages=[{"role": "user", "content": "delete everything"}],
        )
        http_request = AsyncMock()
        http_request.is_disconnected = AsyncMock(return_value=False)

        confirmation = {"tools": [{"name": "ingest_arxiv_papers", "args": {}}]}

        with patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new_callable=AsyncMock,
            side_effect=GraphInterrupt(interrupts=[MagicMock(value=confirmation)]),
        ):
            events = [
                chunk
                async for chunk in stream_event_generator(
                    request_body, http_request, _make_user()
                )
            ]

        assert any("event: confirmation" in e for e in events)
        assert not any("event: error" in e for e in events)


class TestBackgroundTimeout:
    """Bug 5 — background graph.ainvoke must time out after 360s."""

    async def test_run_agent_graph_marks_failed_on_timeout(self):
        from src.api.agent.execute import AgentExecuteRequest, _get_job, _set_job
        from src.api.agent.jobs import _run_agent_graph

        job_id = str(uuid4())
        user = _make_user()
        db = AsyncMock()

        _set_job(
            job_id,
            {
                "status": "running",
                "tool_executions": [],
                "user_id": str(user.id),
                "request": {
                    "messages": [{"role": "user", "content": "hi"}],
                    "page_context": {"type": "unknown"},
                    "model": "gpt-4o",
                    "use_rag": True,
                    "max_context_docs": 5,
                },
            },
        )

        request = AgentExecuteRequest(
            messages=[{"role": "user", "content": "hi"}],
            page_context={"type": "unknown"},
        )

        async def hang_forever(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mock_graph = MagicMock()
        mock_graph.ainvoke = hang_forever

        with (
            patch(
                "src.services.agent.checkpointer.get_checkpointer",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.agent.graph.compile_agent_graph",
                return_value=mock_graph,
            ),
            patch(
                "src.api.agent.jobs.AsyncSessionLocal",
                return_value=_session_cm(db),
            ),
            patch("src.api.agent.jobs.asyncio.timeout") as mock_timeout,
        ):
            mock_timeout.return_value.__aenter__ = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_timeout.return_value.__aexit__ = AsyncMock(return_value=False)
            await _run_agent_graph(job_id, request, user)

        job = _get_job(job_id)
        assert job is not None
        assert job["status"] == "failed"
        assert "timed out" in job["error"].lower()


class TestCheckpointerFallbackLog:
    """Bug 8 — MemorySaver fallback must log at ERROR."""

    async def test_postgres_failure_logs_error(self, caplog):
        from src.services.agent import checkpointer

        checkpointer._checkpointer = None

        with (
            patch(
                "langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string",
                side_effect=RuntimeError("connection refused"),
            ),
            caplog.at_level(logging.ERROR),
        ):
            cp = await checkpointer.get_checkpointer()

        assert cp is not None
        assert any(
            "MemorySaver" in r.message and r.levelno >= logging.ERROR
            for r in caplog.records
        )

        checkpointer._checkpointer = None


class TestFilteredToolNodeErrorInfo:
    """Bug 6 — filtered_tool_node must propagate last_error_info."""

    async def test_filtered_tool_node_returns_last_error_info(self):
        from langchain_core.messages import AIMessage, ToolMessage

        from src.services.agent.graph import make_filtered_tool_node

        node = make_filtered_tool_node({"search_arxiv"})
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc1", "name": "search_arxiv", "args": {"query": "x"}},
            ],
        )
        state = {
            "messages": [ai_msg],
            "tool_executions": [],
            "error_count": 0,
            "last_error": "",
            "last_error_info": {},
            "page_context": {},
            "tool_loop_count": 0,
        }
        config = {
            "configurable": {
                "current_user": Mock(id=uuid4()),
                "db": AsyncMock(),
            }
        }

        error_info = {
            "category": "transient",
            "message": "timeout",
            "suggestion": "retry",
        }

        with patch(
            "src.services.agent.graph._execute_single_tool",
            new_callable=AsyncMock,
            return_value={
                "message": ToolMessage(
                    content='{"error": "timeout"}', tool_call_id="tc1"
                ),
                "execution": {
                    "id": "tc1",
                    "tool_name": "search_arxiv",
                    "tool_display_name": "Search Arxiv",
                    "args": {},
                    "status": "failed",
                    "result": {},
                    "duration_ms": 1,
                },
                "error_increment": 1,
                "error_text": "timeout",
                "error_info": error_info,
            },
        ):
            result = await node(state, config)

        assert result["last_error_info"] == error_info
