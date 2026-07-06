"""Unit tests for arXiv query sanitisation and relevance-sort default.

Covers:
- ``_sanitize_arxiv_query``: strips filler/recency words without clobbering
  meaningful tokens, and falls back to the original when all tokens are noise.
- ``_tool_search_arxiv``: passes a sanitised query and ``sort_by="relevance"``
  to the service by default, and ``sort_by="submittedDate"`` when
  ``chronological=True`` is requested.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.api.agent.tools_impl import _sanitize_arxiv_query, _tool_search_arxiv

# ---------------------------------------------------------------------------
# _sanitize_arxiv_query
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sanitize_strips_recency_filler_words() -> None:
    result = _sanitize_arxiv_query("recent papers on retrieval-augmented generation")
    assert result == "retrieval-augmented generation"


@pytest.mark.unit
def test_sanitize_strips_leading_latest() -> None:
    result = _sanitize_arxiv_query("latest RAG papers")
    assert result == "RAG"


@pytest.mark.unit
def test_sanitize_preserves_clean_query() -> None:
    result = _sanitize_arxiv_query("transformers")
    assert result == "transformers"


@pytest.mark.unit
def test_sanitize_all_stopwords_returns_original() -> None:
    """If every token is a stopword the original is returned unchanged."""
    query = "recent papers on the"
    result = _sanitize_arxiv_query(query)
    assert result == query


# ---------------------------------------------------------------------------
# _tool_search_arxiv — sort and query sanitisation via mocked service
# ---------------------------------------------------------------------------


def _make_service_mock() -> AsyncMock:
    """Return an async-context-manager mock whose search_papers returns one paper."""
    paper = {
        "id": "2401.00001",
        "title": "RAG survey",
        "authors": ["A. Author"],
        "abstract": "A survey of retrieval-augmented generation.",
        "published": "2024-01-01",
        "categories": ["cs.AI"],
        "pdf_url": "https://arxiv.org/pdf/2401.00001",
    }
    service = AsyncMock()
    service.search_papers = AsyncMock(return_value=[paper])
    return service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_search_arxiv_uses_relevance_sort_by_default() -> None:
    """Default call should pass sort_by='relevance' and a sanitised query."""
    service = _make_service_mock()

    # ArXivIngestionService is imported lazily inside the function body, so
    # patch it at its definition site (the module it lives in).
    with (
        patch("src.services.arxiv.arxiv_service.ArXivIngestionService") as mock_cls,
        patch(
            "src.api.agent.tools_impl._arxiv_cache_get",
            return_value=None,
        ),
        patch("src.api.agent.tools_impl._arxiv_cache_set"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=service)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await _tool_search_arxiv({"query": "recent papers on RAG"})

    assert "papers" in result
    _call = service.search_papers.call_args
    # sort_by must be 'relevance' (not 'submittedDate')
    assert _call.kwargs.get("sort_by") == "relevance"
    # The composed query sent to arXiv must not contain the stripped words
    sent_query: str = _call.kwargs.get("query", "") or _call.args[0]
    assert "recent" not in sent_query
    assert "papers" not in sent_query
    assert "on" not in sent_query
    # The topic keyword must survive
    assert "RAG" in sent_query
    # The date-window filter must still be present
    assert "submittedDate:" in sent_query


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_search_arxiv_chronological_uses_date_sort() -> None:
    """chronological=True must flip sort_by to 'submittedDate'."""
    service = _make_service_mock()

    # ArXivIngestionService is imported lazily inside the function body, so
    # patch it at its definition site (the module it lives in).
    with (
        patch("src.services.arxiv.arxiv_service.ArXivIngestionService") as mock_cls,
        patch(
            "src.api.agent.tools_impl._arxiv_cache_get",
            return_value=None,
        ),
        patch("src.api.agent.tools_impl._arxiv_cache_set"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=service)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await _tool_search_arxiv({"query": "X", "chronological": True})

    _call = service.search_papers.call_args
    assert _call.kwargs.get("sort_by") == "submittedDate"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_search_arxiv_empty_results_include_honest_warning() -> None:
    """Empty arXiv searches must surface a warning instead of silent success."""
    service = AsyncMock()
    service.search_papers = AsyncMock(return_value=[])

    with (
        patch("src.services.arxiv.arxiv_service.ArXivIngestionService") as mock_cls,
        patch(
            "src.api.agent.tools_impl._arxiv_cache_get",
            return_value=None,
        ),
        patch("src.api.agent.tools_impl._arxiv_cache_set") as cache_set,
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=service)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await _tool_search_arxiv({"query": "nonexistent topic"})

    assert result["papers"] == []
    assert result["total"] == 0
    assert "warning" in result
    assert "No arXiv papers matched" in result["warning"]
    assert "do not claim" in result["warning"]
    cached_payload = cache_set.call_args.args[1]
    assert cached_payload["warning"] == result["warning"]
