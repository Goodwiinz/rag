"""Tests for cohere_rescore_chunks (src/services/do_kb/rerank.py) and its
flag-gated call sites in _nodes_rag.py / tools_impl.py.

Passthrough behavior (never raises, never drops chunks) is the load-bearing
contract here — DO KB reranking is a reordering nicety, not a retrieval path,
so any failure mode must degrade to the original chunk order.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.do_kb.models import Chunk
from src.services.do_kb.rerank import cohere_rescore_chunks


def _rerank_result(index: int, relevance_score: float) -> MagicMock:
    r = MagicMock()
    r.index = index
    r.relevance_score = relevance_score
    return r


@pytest.mark.unit
async def test_fewer_than_two_chunks_passthrough_service_not_called():
    chunks = [Chunk(text="only one", score=1.0, document_id="a", metadata={})]

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service"
    ) as mock_service:
        result = await cohere_rescore_chunks("q", chunks)

    assert result == chunks
    mock_service.rerank.assert_not_called()


@pytest.mark.unit
async def test_service_disabled_passthrough_original_scores_intact():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=False)
    mock_service.rerank = AsyncMock()

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert result == chunks
    assert [c.score for c in result] == [0.9, 0.5]
    mock_service.rerank.assert_not_called()


@pytest.mark.unit
async def test_success_reorders_and_replaces_scores_without_mutating_input():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=True, last_failure=None)
    # Cohere thinks "b" (index 1) is more relevant than "a" (index 0).
    mock_service.rerank = AsyncMock(
        return_value=[_rerank_result(1, 0.95), _rerank_result(0, 0.2)]
    )

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert len(result) == 2
    assert [c.document_id for c in result] == ["b", "a"]
    assert [c.score for c in result] == [0.95, 0.2]
    # Original input objects untouched (model_copy, not in-place mutation).
    assert chunks[0].score == 0.9
    assert chunks[1].score == 0.5


@pytest.mark.unit
async def test_last_failure_set_after_call_passthrough():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=True, last_failure={"reason": "circuit_open"})
    mock_service.rerank = AsyncMock(
        return_value=[_rerank_result(0, 0.9), _rerank_result(1, 0.5)]
    )

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert result == chunks


@pytest.mark.unit
async def test_timeout_passthrough():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=True, last_failure=None)

    async def _hangs(*args, **kwargs):
        raise asyncio.TimeoutError()

    mock_service.rerank = AsyncMock(side_effect=_hangs)

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert result == chunks


@pytest.mark.unit
async def test_partial_results_covered_first_leftovers_in_original_order():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
        Chunk(text="c", score=0.3, document_id="c", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=True, last_failure=None)
    # Only index 2 ("c") came back from Cohere; 0 and 1 are uncovered.
    mock_service.rerank = AsyncMock(return_value=[_rerank_result(2, 0.99)])

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert len(result) == 3
    assert [c.document_id for c in result] == ["c", "a", "b"]
    assert result[0].score == 0.99


# -- Call-site wiring: _tool_do_kb_retrieve (src/api/agent/tools_impl.py) ----


@pytest.mark.unit
async def test_tool_do_kb_retrieve_flag_on_calls_rerank_and_reflects_scores():
    from src.api.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.client import DOKnowledgeBaseError  # noqa: F401
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="a", score=0.9, document_id="a.pdf", metadata={}),
                Chunk(text="b", score=0.5, document_id="b.pdf", metadata={}),
            ],
            total=2,
        )
    )

    reranked_chunks = [
        Chunk(text="b", score=0.99, document_id="b.pdf", metadata={}),
        Chunk(text="a", score=0.1, document_id="a.pdf", metadata={}),
    ]
    mock_rescore = AsyncMock(return_value=reranked_chunks)

    with (
        patch(
            "src.core.config.settings",
            MagicMock(
                DO_KB_ENABLED=True,
                AGENT_DOKB_COHERE_RERANK=True,
                AGENT_ITERATIVE_RETRIEVAL=False,
            ),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch("src.services.do_kb.rerank.cohere_rescore_chunks", mock_rescore),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    mock_rescore.assert_awaited_once()
    assert [c["document_id"] for c in result["chunks"]] == ["b.pdf", "a.pdf"]
    assert result["chunks"][0]["score"] == 0.99


@pytest.mark.unit
async def test_tool_do_kb_retrieve_flag_off_never_imports_rerank():
    from src.api.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="a", score=0.9, document_id="a.pdf", metadata={}),
                Chunk(text="b", score=0.5, document_id="b.pdf", metadata={}),
            ],
            total=2,
        )
    )

    with (
        patch(
            "src.core.config.settings",
            MagicMock(
                DO_KB_ENABLED=True,
                AGENT_DOKB_COHERE_RERANK=False,
                AGENT_ITERATIVE_RETRIEVAL=False,
            ),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch("src.services.do_kb.rerank.cohere_rescore_chunks") as mock_rescore,
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    mock_rescore.assert_not_called()
    assert [c["document_id"] for c in result["chunks"]] == ["a.pdf", "b.pdf"]
    assert [c["score"] for c in result["chunks"]] == [0.9, 0.5]


# -- Call-site wiring: evidence_mode / summarize_evidence (PR-2) -------------


@pytest.mark.unit
async def test_tool_do_kb_retrieve_evidence_flag_on_calls_summarize_evidence():
    from src.api.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="a", score=0.9, document_id="a.pdf", metadata={})],
            total=1,
        )
    )

    enriched_payload = [
        {
            "text": "a",
            "score": 0.9,
            "document_id": "a.pdf",
            "title": "a.pdf",
            "metadata": {},
            "relevance": 8,
            "summary": "on point",
            "quote": "a",
        }
    ]
    mock_summarize = AsyncMock(return_value=enriched_payload)

    with (
        patch(
            "src.core.config.settings",
            MagicMock(
                DO_KB_ENABLED=True,
                AGENT_DOKB_COHERE_RERANK=False,
                AGENT_ITERATIVE_RETRIEVAL=True,
            ),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch("src.services.agent.evidence.summarize_evidence", mock_summarize),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    mock_summarize.assert_awaited_once()
    call_args = mock_summarize.call_args.args
    assert call_args[0] == "x"
    assert call_args[1] == [
        {
            "text": "a",
            "score": 0.9,
            "document_id": "a.pdf",
            "title": "a.pdf",
            "metadata": {},
        }
    ]
    assert result["evidence_mode"] is True
    assert result["chunks"] == enriched_payload


@pytest.mark.unit
async def test_tool_do_kb_retrieve_evidence_flag_off_never_calls_summarize_evidence():
    from src.api.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="a", score=0.9, document_id="a.pdf", metadata={})],
            total=1,
        )
    )

    with (
        patch(
            "src.core.config.settings",
            MagicMock(
                DO_KB_ENABLED=True,
                AGENT_DOKB_COHERE_RERANK=False,
                AGENT_ITERATIVE_RETRIEVAL=False,
            ),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch("src.services.agent.evidence.summarize_evidence") as mock_summarize,
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    mock_summarize.assert_not_called()
    assert result["evidence_mode"] is False
