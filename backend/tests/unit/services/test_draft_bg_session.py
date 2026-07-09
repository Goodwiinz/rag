"""`_generate_draft_async` must own its own session, not the caller's.

`generate_draft` fire-and-forgets `_generate_draft_async` in the background and
returns immediately; the caller (`_tool_create_draft` / the REST 202 path) then
exits its own session scope before the background task's first DB call runs.
Using `self.db` inside the background task therefore raced a session the
caller had already closed. `_generate_draft_async` now opens its own
`AsyncSessionLocal()` and never touches `self.db` (the ctor-injected,
request-scoped session used only by the request-scoped methods).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

from src.services.research.draft_generation_service import (
    DraftGenerationService,
    DraftGenerationStatus,
    _generation_status,
)


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch(
        "src.services.research.draft_generation_service.asyncio.sleep",
        new=AsyncMock(),
    ):
        yield


def _make_bg_session(documents):
    """A MagicMock session with just the async methods the background task
    calls actually mocked as AsyncMock (add() is sync on AsyncSession)."""
    session = MagicMock()

    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = documents
    version_result = MagicMock()
    version_result.scalar.return_value = 0
    update_result = MagicMock()

    session.execute = AsyncMock(
        side_effect=[docs_result, version_result, update_result]
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _patch_session_factory(bg_session):
    patcher = patch("src.services.research.draft_generation_service.AsyncSessionLocal")
    session_factory = patcher.start()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=bg_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher


async def _run(service, task_id, project_id=None, user_id=None):
    project_id = project_id or uuid4()
    user_id = user_id or uuid4()
    _generation_status[task_id] = {
        "status": DraftGenerationStatus.PENDING,
        "progress": 0,
        "current_step": "Initializing",
        "project_id": str(project_id),
        "user_id": str(user_id),
    }
    await service._generate_draft_async(
        task_id=task_id,
        project_id=project_id,
        user_id=user_id,
        themes=["theme a"],
        document_ids=None,
        style="academic",
        max_sections=5,
        include_abstract=True,
    )


@pytest.mark.asyncio
async def test_background_task_never_touches_ctor_session():
    ctor_session = MagicMock()  # the caller's (already-closed) session
    documents = [MagicMock(id=uuid4(), title="Doc A")]
    bg_session = _make_bg_session(documents)

    service = DraftGenerationService(ctor_session)
    service._build_draft_content = AsyncMock(return_value="Some draft body.")

    patcher = _patch_session_factory(bg_session)
    try:
        await _run(service, "task-own-session")
    finally:
        patcher.stop()

    ctor_session.execute.assert_not_called()
    bg_session.execute.assert_awaited()
    bg_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_happy_path_completes_through_patched_session():
    documents = [MagicMock(id=uuid4(), title="Doc A")]
    bg_session = _make_bg_session(documents)

    service = DraftGenerationService(MagicMock())
    service._build_draft_content = AsyncMock(return_value="Findings from [Doc 1].")

    patcher = _patch_session_factory(bg_session)
    try:
        await _run(service, "task-happy")
    finally:
        patcher.stop()

    status = DraftGenerationService.get_status("task-happy")
    assert status["status"] == DraftGenerationStatus.COMPLETED
    bg_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_documents_fails_without_committing():
    bg_session = _make_bg_session([])

    service = DraftGenerationService(MagicMock())

    patcher = _patch_session_factory(bg_session)
    try:
        await _run(service, "task-empty")
    finally:
        patcher.stop()

    status = DraftGenerationService.get_status("task-empty")
    assert status["status"] == DraftGenerationStatus.FAILED
    bg_session.commit.assert_not_awaited()
