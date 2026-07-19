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
        result = await _tool_summarize_document(
            {"document_id": "2303.15563"}, db, user
        )

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

    with patch(
        "src.api.agent.tools_impl._resolve_document_id",
        new=AsyncMock(return_value=None),
    ):
        result = await _tool_summarize_document(
            {"document_id": "some-random-title"}, db, user
        )

    assert result["error"] == "Document not found or access denied"
    assert "error_type" not in result
