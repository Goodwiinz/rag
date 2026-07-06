"""Outcome-labeled metrics on the DO KB primary-read path (FIX A2 + A1/A3).

`_try_primary_do_kb_read` emits `rag_do_kb_read_total{outcome=...}` at each
return point so a deleted KB (404) is observable instead of silent. These tests
spy on the single choke point `_record_do_kb_read` and assert the right label
fires for a success and for a 404 — and that a 404 still returns None (the
fallback is preserved). The KB client + DB session are mocked; no embedding or
in-pod code runs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent import _nodes_rag
from src.services.do_kb.client import DOKnowledgeBaseError
from src.services.do_kb.models import Chunk, RetrieveResult


def _fake_session_ctx(org):
    """An async-context-manager factory returning a session whose .get -> org."""
    session = MagicMock()
    session.get = AsyncMock(return_value=org)

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


@pytest.fixture
def kb_cfg():
    cfg = MagicMock()
    cfg.DO_KB_PRIMARY_READ = True
    cfg.DO_KB_RETRIEVE_TIMEOUT_SECONDS = 5.0
    return cfg


@pytest.mark.unit
@pytest.mark.asyncio
async def test_success_emits_success_outcome(kb_cfg, monkeypatch):
    user = MagicMock()
    user.organization_id = "org-1"
    user.id = "u-1"

    org = MagicMock()
    org.do_kb_uuid = "kb-1"

    client = MagicMock()
    client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="hi", score=0.9, document_id="doc-1", metadata={})],
            total=1,
        )
    )

    recorded: list[str] = []
    monkeypatch.setattr(_nodes_rag, "_record_do_kb_read", recorded.append)

    # No project scope → resolve_and_filter_chunks returns title map + chunks.
    async def fake_resolve(*, chunks, org_id, session, project_id):
        return ({}, chunks)

    with (
        patch("src.core.config.settings", kb_cfg),
        patch(
            "src.core.database.AsyncSessionLocal",
            _fake_session_ctx(org),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=client),
        patch(
            "src.services.do_kb.resolve.resolve_and_filter_chunks",
            fake_resolve,
        ),
    ):
        result = await _nodes_rag._try_primary_do_kb_read("q", user, project_id=None)

    assert result is not None and len(result) == 1
    assert "success" in recorded


@pytest.mark.unit
@pytest.mark.asyncio
async def test_404_emits_error_outcome_and_returns_none(kb_cfg, monkeypatch):
    user = MagicMock()
    user.organization_id = "org-1"
    user.id = "u-1"

    org = MagicMock()
    org.do_kb_uuid = "kb-1"

    client = MagicMock()
    client.retrieve = AsyncMock(
        side_effect=DOKnowledgeBaseError("gone", status_code=404)
    )

    recorded: list[str] = []
    monkeypatch.setattr(_nodes_rag, "_record_do_kb_read", recorded.append)

    with (
        patch("src.core.config.settings", kb_cfg),
        patch("src.core.database.AsyncSessionLocal", _fake_session_ctx(org)),
        patch("src.services.do_kb.get_do_kb_client", return_value=client),
    ):
        result = await _nodes_rag._try_primary_do_kb_read("q", user, project_id=None)

    # Fallback preserved (None), and the 404 is observable.
    assert result is None
    assert "do_kb_error_404" in recorded
    assert "do_kb_error_other" not in recorded


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_kb_emits_do_kb_empty(kb_cfg, monkeypatch):
    """KB up but no matches is a healthy outcome, distinct from an error."""
    user = MagicMock()
    user.organization_id = "org-1"
    user.id = "u-1"

    org = MagicMock()
    org.do_kb_uuid = "kb-1"

    client = MagicMock()
    client.retrieve = AsyncMock(return_value=RetrieveResult(chunks=[], total=0))

    recorded: list[str] = []
    monkeypatch.setattr(_nodes_rag, "_record_do_kb_read", recorded.append)

    with (
        patch("src.core.config.settings", kb_cfg),
        patch("src.core.database.AsyncSessionLocal", _fake_session_ctx(org)),
        patch("src.services.do_kb.get_do_kb_client", return_value=client),
    ):
        result = await _nodes_rag._try_primary_do_kb_read("q", user, project_id=None)

    assert result is None
    assert "do_kb_empty" in recorded
