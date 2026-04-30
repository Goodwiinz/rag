"""Tests for WC-1 / WC-2 hardening in jobs.py.

Covers:

* WC-1: ``_clear_stale_pending_confirmation`` also resets the per-turn
  ephemeral counters (``tool_loop_count``, ``error_count``,
  ``reflection_count``) so stale state from an abandoned turn cannot bleed
  into the next turn even if a future graph refactor stops running
  ``preprocessing_node`` on the resume path.
* WC-2: ``_resume_agent_graph`` short-circuits when the snapshot no longer
  contains a ``pending_confirmation`` (the interrupt has already been
  consumed). The existing ``_jobs_lock`` in ``confirm_agent_action`` already
  prevents a double-resume race; this is the in-depth guard for the
  resume-side.
* The existing double-confirm invariant: a second ``POST /confirm/{id}``
  while the job is in ``running`` returns HTTP 400.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.agent.execute import router
from src.api.agent.jobs import (
    _clear_stale_pending_confirmation,
    _get_job,
    _resume_agent_graph,
    _set_job,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot(values: dict) -> SimpleNamespace:
    """Build a minimal LangGraph snapshot stub with the given values."""
    return SimpleNamespace(values=values)


def _make_graph(snapshot_values: dict | None) -> Mock:
    graph = Mock()
    graph.aget_state = AsyncMock(
        return_value=_snapshot(snapshot_values) if snapshot_values is not None else None
    )
    graph.aupdate_state = AsyncMock()
    graph.ainvoke = AsyncMock(return_value={"messages": [], "tool_executions": []})
    return graph


def _make_mock_user(user_id: str = "user-aaa"):
    user = Mock()
    user.id = user_id
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = Mock(value="user")
    user.organization_id = "test-org"
    user.is_active = True
    return user


@asynccontextmanager
async def _async_session_cm():
    """Async context manager that yields a mocked AsyncSession."""
    yield AsyncMock()


# ---------------------------------------------------------------------------
# WC-1: defensive reset in _clear_stale_pending_confirmation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_stale_pending_confirmation_resets_counters():
    """When wiping a stale interrupt, also reset tool/error/reflection counters."""
    graph = _make_graph(
        {
            "pending_confirmation": {"tools": [{"name": "ingest_arxiv_papers"}]},
            "user_confirmed": False,
            "tool_loop_count": 5,
            "error_count": 2,
            "reflection_count": 1,
        }
    )
    config = {"configurable": {"thread_id": "thread-abc"}}

    cleared = await _clear_stale_pending_confirmation(graph, config)

    assert cleared is True
    graph.aupdate_state.assert_awaited_once()
    args, _kwargs = graph.aupdate_state.call_args
    assert args[0] is config
    assert args[1] == {
        "pending_confirmation": {},
        "user_confirmed": False,
        "tool_loop_count": 0,
        "error_count": 0,
        "reflection_count": 0,
    }


@pytest.mark.asyncio
async def test_clear_stale_pending_confirmation_skips_when_no_interrupt():
    """When no pending_confirmation exists, the helper is a no-op."""
    graph = _make_graph(
        {
            "pending_confirmation": {},
            "tool_loop_count": 3,  # noisy but should not be touched
        }
    )
    config = {"configurable": {"thread_id": "thread-xyz"}}

    cleared = await _clear_stale_pending_confirmation(graph, config)

    assert cleared is False
    graph.aupdate_state.assert_not_called()


# ---------------------------------------------------------------------------
# WC-2: idempotency guard in _resume_agent_graph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_short_circuits_when_interrupt_already_consumed():
    """If the checkpoint has no pending_confirmation, resume must not call ainvoke.

    Simulates the race the audit flagged: a stale background resume task
    fires after the interrupt has already been answered. ``Command(resume=...)``
    would have nothing to resume against.
    """
    user = _make_mock_user()
    job_id = str(uuid4())
    _set_job(
        job_id,
        {
            "status": "running",
            "user_id": str(user.id),
            "tool_executions": [],
        },
    )

    graph = _make_graph({"user_id": str(user.id), "pending_confirmation": {}})

    with (
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch("src.api.agent.jobs.AsyncSessionLocal", return_value=_async_session_cm()),
    ):
        await _resume_agent_graph(job_id, confirmed=True, current_user=user)

    graph.ainvoke.assert_not_called()
    job = _get_job(job_id)
    assert job is not None
    assert job["status"] == "error"
    assert "already consumed" in (job.get("error") or "").lower()


@pytest.mark.asyncio
async def test_resume_proceeds_when_interrupt_present():
    """When the snapshot still has pending_confirmation, resume reaches ainvoke."""
    user = _make_mock_user()
    job_id = str(uuid4())
    _set_job(
        job_id,
        {
            "status": "running",
            "user_id": str(user.id),
            "tool_executions": [],
        },
    )

    graph = _make_graph(
        {
            "user_id": str(user.id),
            "pending_confirmation": {"tools": [{"name": "ingest_arxiv_papers"}]},
        }
    )

    with (
        patch("src.services.agent.graph.compile_agent_graph", return_value=graph),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=None),
        ),
        patch("src.api.agent.jobs.AsyncSessionLocal", return_value=_async_session_cm()),
        patch(
            "src.api.agent.jobs._persist_thread_messages",
            new=AsyncMock(return_value=("", "")),
        ),
    ):
        await _resume_agent_graph(job_id, confirmed=True, current_user=user)

    graph.ainvoke.assert_awaited_once()


# ---------------------------------------------------------------------------
# Existing double-confirm invariant — protected by _jobs_lock
# ---------------------------------------------------------------------------


@pytest.fixture
def confirm_client():
    """FastAPI test client with the agent router and dependency overrides."""
    from src.core.database import get_db
    from src.core.dependencies import get_current_user

    user = _make_mock_user()

    app = FastAPI()
    app.include_router(router)

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=Mock(return_value=None))
        )
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    app.router.lifespan_context = _no_lifespan
    with TestClient(app) as client:
        yield client, user


def test_double_confirm_second_request_returns_400(confirm_client):
    """Second POST /confirm/{id} after the first flips status to running returns 400.

    This is the existing _jobs_lock invariant — included so a future
    refactor that loosens the lock fails this test loudly.
    """
    client, user = confirm_client
    job_id = str(uuid4())
    _set_job(
        job_id,
        {
            "status": "awaiting_confirmation",
            "confirmation": {"tools": [], "message": "Confirm?"},
            "tool_executions": [],
            "user_id": str(user.id),
        },
    )

    with patch("src.api.agent.execute._resume_agent_graph", new_callable=AsyncMock):
        first = client.post(f"/api/v1/agent/confirm/{job_id}", json={"confirmed": True})
        second = client.post(
            f"/api/v1/agent/confirm/{job_id}", json={"confirmed": True}
        )

    assert first.status_code == 200
    assert first.json()["status"] == "running"
    assert second.status_code == 400
