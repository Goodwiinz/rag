"""Phase 4 regression — _resolve_document_id accepts arXiv IDs.

Trace 019e1569 showed `summarize_document(document_id="2303.15563")`
returning ``"Document not found or access denied"`` because the resolver
only matched UUIDs or titles. The fix adds an arXiv-ID branch that
matches against ``Document.filename`` or ``document_metadata->>'arxiv_id'``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.agent.tool_helpers import _ARXIV_ID_RE, _resolve_document_id


@pytest.mark.unit
def test_arxiv_regex_matches_known_forms():
    assert _ARXIV_ID_RE.match("2303.15563")
    assert _ARXIV_ID_RE.match("2303.15563v1")
    assert _ARXIV_ID_RE.match("2303.15563v23")
    assert _ARXIV_ID_RE.match("0704.0001")  # 4-digit suffix variant


@pytest.mark.unit
def test_arxiv_regex_rejects_non_arxiv():
    assert _ARXIV_ID_RE.match("not-an-arxiv-id") is None
    assert _ARXIV_ID_RE.match("123") is None
    assert _ARXIV_ID_RE.match("12345.678") is None  # 5-digit year not allowed
    # Trailing junk
    assert _ARXIV_ID_RE.match("2303.15563.pdf") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_arxiv_id_matches_filename():
    """Bare arXiv ID matches a Document whose filename embeds the ID."""
    user = MagicMock()
    user.organization_id = "org-1"

    matching_doc = MagicMock()
    matching_doc.id = "uuid-1"
    matching_doc.title = "Privacy-preserving ML for healthcare"
    matching_doc.filename = "2303.15563.pdf"

    db = MagicMock()
    # First UUID-parse attempt is skipped by the resolver because the ID
    # isn't a valid UUID; the arxiv branch is the first DB hit.
    arxiv_result = MagicMock()
    arxiv_result.scalar_one_or_none = MagicMock(return_value=matching_doc)
    db.execute = AsyncMock(return_value=arxiv_result)

    result = await _resolve_document_id("2303.15563", db, user)
    assert result is matching_doc
    db.execute.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_arxiv_id_with_version_strips_to_bare_id():
    user = MagicMock()
    user.organization_id = "org-1"

    matching_doc = MagicMock()
    matching_doc.filename = "2303.15563.pdf"

    db = MagicMock()
    arxiv_result = MagicMock()
    arxiv_result.scalar_one_or_none = MagicMock(return_value=matching_doc)
    db.execute = AsyncMock(return_value=arxiv_result)

    result = await _resolve_document_id("2303.15563v1", db, user)
    assert result is matching_doc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_arxiv_id_not_in_library_returns_none():
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    empty_result = MagicMock()
    empty_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=empty_result)

    result = await _resolve_document_id("2303.15563", db, user)
    assert result is None
