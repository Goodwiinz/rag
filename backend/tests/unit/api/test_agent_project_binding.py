"""
Unit tests for jobs._resolve_and_bind_project.

The chat UI binds projects to its workspace thread while agent runs execute
on a separate agent thread; this resolver bridges the two and durably adopts
the binding onto the agent thread. See the helper docstring for the three
resolution paths under test here.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.agent.jobs import _resolve_and_bind_project


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid4()
    return user


@pytest.fixture
def agent_thread():
    thread = MagicMock()
    thread.id = uuid4()
    thread.source_project_id = None
    return thread


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _result(first=None, scalar=None):
    r = MagicMock()
    r.first.return_value = first
    r.scalar_one_or_none.return_value = scalar
    return r


@pytest.mark.asyncio
async def test_owned_client_project_fills_context_and_binds_thread(
    mock_user, agent_thread, mock_db
):
    """Path 1: owned page_context.project_id is kept and attached to the thread."""
    project_id = uuid4()
    page_context = {"type": "chat", "project_id": str(project_id)}

    # Ownership query returns (id, name)
    mock_db.execute.return_value = _result(first=(project_id, "My Project"))

    with patch(
        "src.services.research.project_thread_service.attach_thread_to_project",
        new=AsyncMock(),
    ) as attach:
        await _resolve_and_bind_project(mock_db, mock_user, agent_thread, page_context)

    assert page_context["project_id"] == str(project_id)
    assert page_context["project_name"] == "My Project"
    assert page_context["type"] == "project"
    attach.assert_awaited_once()
    assert attach.await_args.args[2] == project_id
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_unowned_client_project_is_dropped(mock_user, agent_thread, mock_db):
    """Path 1: a project the caller does not own must not scope the turn."""
    page_context = {"type": "chat", "project_id": str(uuid4())}

    # Ownership query finds nothing; thread fallback (path 2) and the
    # workspace bridge (path 3) find nothing either.
    mock_db.execute.return_value = _result(first=None)

    with patch(
        "src.api.agent.jobs._resolve_project_for_thread",
        new=AsyncMock(return_value=(None, None)),
    ), patch(
        "src.services.research.project_thread_service.attach_thread_to_project",
        new=AsyncMock(),
    ) as attach:
        await _resolve_and_bind_project(mock_db, mock_user, agent_thread, page_context)

    assert page_context["project_id"] is None
    attach.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_linked_thread_resolves_without_reattach(
    mock_user, agent_thread, mock_db
):
    """Path 2: a linked agent thread resolves directly and is not re-attached."""
    project_id = uuid4()
    agent_thread.source_project_id = project_id
    page_context = {"type": "chat"}

    with patch(
        "src.api.agent.jobs._resolve_project_for_thread",
        new=AsyncMock(return_value=(str(project_id), "Linked Project")),
    ), patch(
        "src.services.research.project_thread_service.attach_thread_to_project",
        new=AsyncMock(),
    ) as attach:
        await _resolve_and_bind_project(mock_db, mock_user, agent_thread, page_context)

    assert page_context["project_id"] == str(project_id)
    assert page_context["project_name"] == "Linked Project"
    attach.assert_not_awaited()


@pytest.mark.asyncio
async def test_workspace_thread_bridge_resolves_and_binds_agent_thread(
    mock_user, agent_thread, mock_db
):
    """Path 3: the workspace thread's binding is adopted by the agent thread.

    This is the regression the resolver exists for: project bound to the
    workspace thread, agent running on a different thread, no URL param.
    """
    project_id = uuid4()
    ws_thread = MagicMock()
    ws_thread.id = uuid4()
    page_context = {
        "type": "chat",
        "metadata": {"workspace_thread_id": str(ws_thread.id)},
    }

    # The only direct db.execute here is the owner-checked workspace thread
    # lookup; _resolve_project_for_thread is patched per-thread.
    mock_db.execute.return_value = _result(scalar=ws_thread)

    async def resolve(db, thread):
        if thread is ws_thread:
            return str(project_id), "Bound Project"
        return None, None

    with patch(
        "src.api.agent.jobs._resolve_project_for_thread",
        new=AsyncMock(side_effect=resolve),
    ), patch(
        "src.services.research.project_thread_service.attach_thread_to_project",
        new=AsyncMock(),
    ) as attach:
        await _resolve_and_bind_project(mock_db, mock_user, agent_thread, page_context)

    assert page_context["project_id"] == str(project_id)
    assert page_context["project_name"] == "Bound Project"
    assert page_context["type"] == "project"
    # The AGENT thread (not the workspace thread) gets durably linked.
    attach.assert_awaited_once()
    assert attach.await_args.args[1] is agent_thread
    assert attach.await_args.args[2] == project_id


@pytest.mark.asyncio
async def test_attach_failure_never_blocks_the_turn(mock_user, agent_thread, mock_db):
    """A bind failure is best-effort: context is still filled, no raise."""
    project_id = uuid4()
    page_context = {"type": "chat", "project_id": str(project_id)}
    mock_db.execute.return_value = _result(first=(project_id, "My Project"))

    with patch(
        "src.services.research.project_thread_service.attach_thread_to_project",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        await _resolve_and_bind_project(mock_db, mock_user, agent_thread, page_context)

    assert page_context["project_id"] == str(project_id)
    mock_db.rollback.assert_awaited()
