"""Phase 4 regression — summarize_document hints at ingest when arXiv ID
isn't in the library.

Trace 019e1569 showed the agent passing a raw arXiv ID where the tool
expected an internal UUID. Previously the error was the generic
"Document not found or access denied". Now the tool detects the
arXiv-ID pattern and returns a recoverable suggestion to call
``ingest_arxiv_papers`` first.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.agent.tools_impl import _tool_summarize_document


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arxiv_id_not_ingested_returns_recoverable_hint():
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    with patch(
        "src.api.agent.tools_impl._resolve_document_id",
        new=AsyncMock(return_value=None),
    ):
        result = await _tool_summarize_document({"document_id": "2303.15563"}, db, user)

    assert "error" in result
    assert "arXiv" in result["error"]
    assert result.get("error_type") == "recoverable"
    assert result.get("suggestion") == "ingest_arxiv_papers"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arxiv_id_with_version_also_hints():
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    with patch(
        "src.api.agent.tools_impl._resolve_document_id",
        new=AsyncMock(return_value=None),
    ):
        result = await _tool_summarize_document(
            {"document_id": "2303.15563v2"}, db, user
        )

    assert result.get("error_type") == "recoverable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_arxiv_missing_doc_returns_generic_error():
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    with (
        patch(
            "src.api.agent.tools_impl._resolve_document_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.tools_impl._verify_project_ownership",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await _tool_summarize_document(
            {"document_id": "some-random-title"}, db, user
        )

    assert result["error"] == "Document not found or access denied"
    assert "error_type" not in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_project_id_returns_recoverable_list_documents_hint():
    """Trace 019f4386 — agent passed a project id to summarize_document.
    The tool now detects an owned project and steers to
    ``list_project_documents`` instead of the opaque generic error."""
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    project = MagicMock()
    project.id = "e3793259-a949-4dc9-b41b-c9f31c0febe6"
    project.name = "Retrieval-Augmented Generation"

    with (
        patch(
            "src.api.agent.tools_impl._resolve_document_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.api.agent.tools_impl._verify_project_ownership",
            new=AsyncMock(return_value=project),
        ),
    ):
        result = await _tool_summarize_document({"document_id": project.id}, db, user)

    assert result.get("error_type") == "recoverable"
    assert result.get("suggestion") == "list_project_documents"
    assert "project id, not a document id" in result["error"]
    assert project.name in result["error"]
