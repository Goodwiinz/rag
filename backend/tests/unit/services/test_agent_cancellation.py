"""Unit tests for cancellation handling in ``_run_agent_graph`` and
``_resume_agent_graph``.

CancelledError inherits from BaseException (not Exception) since
Python 3.8, so the broad ``except Exception`` clauses in these
runners do NOT catch it. Without explicit handlers the job stayed
stuck in ``"running"`` forever when the background task was
cancelled (client disconnect, server shutdown, parent timeout, etc.).

These tests assert the job is marked ``"cancelled"`` and the
exception is re-raised so the task tears down cleanly.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _make_mock_user(user_id: str = "user-cancel-test"):
    user = Mock()
    user.id = user_id
    user.email = "cancel@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = Mock(value="user")
    user.organization_id = "test-org"
    user.is_active = True
    return user


def _make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=Mock(return_value=None))
    )
    db.add = Mock()
    return db


@asynccontextmanager
async def _async_session_yielding(db):
    yield db


async def test_run_agent_graph_marks_job_cancelled_and_reraises():
    from src.api.agent.execute import AgentExecuteRequest, _set_job, _get_job
    from src.api.agent.jobs import _run_agent_graph

    job_id = str(uuid4())
    user = _make_mock_user()
    db = _make_mock_db()

    # Pre-seed job in "running" state — same as what /execute does.
    _set_job(
        job_id,
        {
            "status": "running",
            "tool_executions": [],
            "user_id": str(user.id),
            "request": {
                "messages": [{"role": "user", "content": "hi"}],
                "page_context": {"type": "unknown"},
                "model": "model-router",
                "use_rag": True,
                "max_context_docs": 5,
            },
        },
    )

    request = AgentExecuteRequest(
        messages=[{"role": "user", "content": "hi"}],
        page_context={"type": "unknown"},
        model="model-router",
        use_rag=True,
        max_context_docs=5,
    )

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
    mock_graph.aget_state = AsyncMock(return_value=None)

    with (
        patch(
            "src.services.agent.checkpointer.get_checkpointer", new_callable=AsyncMock
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph", return_value=mock_graph
        ),
        patch(
            "src.api.agent.jobs.AsyncSessionLocal",
            return_value=_async_session_yielding(db),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _run_agent_graph(job_id, request, user)

    job = _get_job(job_id)
    assert job is not None
    assert job["status"] == "cancelled"
    assert job["error"] == "execution cancelled"


async def test_resume_agent_graph_marks_job_cancelled_and_reraises():
    from src.api.agent.execute import _set_job, _get_job
    from src.api.agent.jobs import _resume_agent_graph

    job_id = str(uuid4())
    user = _make_mock_user()
    db = _make_mock_db()

    _set_job(
        job_id,
        {
            "status": "awaiting_confirmation",
            "tool_executions": [],
            "user_id": str(user.id),
            "request": {
                "messages": [{"role": "user", "content": "ingest paper"}],
                "page_context": {"type": "unknown"},
                "model": "model-router",
                "use_rag": True,
                "max_context_docs": 5,
            },
        },
    )

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
    mock_graph.aget_state = AsyncMock(return_value=None)

    with (
        patch(
            "src.services.agent.checkpointer.get_checkpointer", new_callable=AsyncMock
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph", return_value=mock_graph
        ),
        patch(
            "src.api.agent.jobs.AsyncSessionLocal",
            return_value=_async_session_yielding(db),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await _resume_agent_graph(job_id, True, user)

    job = _get_job(job_id)
    assert job is not None
    assert job["status"] == "cancelled"
    assert job["error"] == "resume cancelled"


async def test_run_agent_graph_still_marks_failed_for_regular_exceptions():
    """Regression check: the new CancelledError handler must not swallow
    plain Exception failures, which still need ``status="failed"``."""
    from src.api.agent.execute import AgentExecuteRequest, _set_job, _get_job
    from src.api.agent.jobs import _run_agent_graph

    job_id = str(uuid4())
    user = _make_mock_user()
    db = _make_mock_db()

    _set_job(
        job_id,
        {
            "status": "running",
            "tool_executions": [],
            "user_id": str(user.id),
            "request": {
                "messages": [{"role": "user", "content": "hi"}],
                "page_context": {"type": "unknown"},
                "model": "model-router",
                "use_rag": True,
                "max_context_docs": 5,
            },
        },
    )

    request = AgentExecuteRequest(
        messages=[{"role": "user", "content": "hi"}],
        page_context={"type": "unknown"},
        model="model-router",
        use_rag=True,
        max_context_docs=5,
    )

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("kaboom"))
    mock_graph.aget_state = AsyncMock(return_value=None)

    with (
        patch(
            "src.services.agent.checkpointer.get_checkpointer", new_callable=AsyncMock
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph", return_value=mock_graph
        ),
        patch(
            "src.api.agent.jobs.AsyncSessionLocal",
            return_value=_async_session_yielding(db),
        ),
    ):
        # Plain Exception is caught — no re-raise.
        await _run_agent_graph(job_id, request, user)

    job = _get_job(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert "kaboom" in job["error"]
