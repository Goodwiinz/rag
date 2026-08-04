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
    assert [c.metadata["score_source"] for c in result] == ["cohere", "cohere"]
    sent_docs = mock_service.rerank.await_args.args[1]
    assert sent_docs == [
        {"content": "a", "id": "0", "score": 0.9},
        {"content": "b", "id": "1", "score": 0.5},
    ]
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
    assert result[0].metadata["score_source"] == "cohere"


@pytest.mark.unit
async def test_invalid_results_passthrough_original_chunks():
    chunks = [
        Chunk(text="a", score=0.9, document_id="a", metadata={}),
        Chunk(text="b", score=0.5, document_id="b", metadata={}),
    ]
    mock_service = MagicMock(is_enabled=True, last_failure=None)
    mock_service.rerank = AsyncMock(return_value=[_rerank_result(9, 0.99)])

    with patch(
        "src.services.search.cohere_rerank_service.cohere_rerank_service",
        mock_service,
    ):
        result = await cohere_rescore_chunks("q", chunks)

    assert result == chunks


@pytest.mark.unit
def test_chunk_from_do_payload_marks_upstream_score_provenance():
    chunk = Chunk.from_do_payload(
        {"text_content": "scored", "score": 0.82, "metadata": {"title": "Doc"}}
    )

    assert chunk.score == 0.82
    assert chunk.metadata == {"title": "Doc", "score_source": "upstream"}


@pytest.mark.unit
def test_chunk_from_do_payload_marks_rank_proxy_provenance():
    chunk = Chunk.from_do_payload(
        {"text_content": "unscored", "metadata": {"title": "Doc"}}, rank=3
    )

    assert chunk.score == 0.85
    assert chunk.metadata == {"title": "Doc", "score_source": "rank_proxy"}


@pytest.mark.unit
def test_cohere_rerank_is_enabled_by_default():
    from src.core.config import Settings

    assert Settings.model_fields["AGENT_DOKB_COHERE_RERANK"].default is True


# -- Call-site wiring: _tool_do_kb_retrieve (src/api/agent/tools_impl.py) ----


@pytest.mark.unit
async def test_tool_do_kb_retrieve_flag_on_sanitizes_before_rerank():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
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
                Chunk(
                    text="Contact synthetic.alpha@example.test",
                    score=0.9,
                    document_id="a.pdf",
                    metadata={"owner": "synthetic.alpha@example.test"},
                ),
                Chunk(
                    text="Contact synthetic.beta@example.test",
                    score=0.8,
                    document_id="duplicate.pdf",
                    metadata={},
                ),
                Chunk(text="Safe content", score=0.5, document_id="b.pdf", metadata={}),
            ],
            total=3,
        )
    )

    async def _rerank_sanitized(_query, chunks):
        assert [chunk.text for chunk in chunks] == [
            "Contact <email>",
            "Safe content",
        ]
        assert chunks[0].metadata["owner"] == "<email>"
        return [
            chunks[1].model_copy(
                update={"score": 0.99, "metadata": {"score_source": "cohere"}}
            ),
            chunks[0].model_copy(
                update={"score": 0.1, "metadata": {"score_source": "cohere"}}
            ),
        ]

    mock_rescore = AsyncMock(side_effect=_rerank_sanitized)

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
    assert result["chunks"][0]["score_source"] == "cohere"
    assert all("synthetic." not in chunk["text"] for chunk in result["chunks"])


@pytest.mark.unit
async def test_tool_do_kb_retrieve_flag_off_still_sanitizes_and_deduplicates():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
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
                Chunk(
                    text="Contact synthetic.alpha@example.test",
                    score=0.9,
                    document_id="a.pdf",
                    metadata={"score_source": "rank_proxy"},
                ),
                Chunk(
                    text="Contact synthetic.beta@example.test",
                    score=0.5,
                    document_id="b.pdf",
                    metadata={"score_source": "rank_proxy"},
                ),
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
    assert [c["document_id"] for c in result["chunks"]] == ["a.pdf"]
    assert [c["text"] for c in result["chunks"]] == ["Contact <email>"]
    assert result["chunks"][0]["score_source"] == "rank_proxy"


@pytest.mark.unit
async def test_tool_do_kb_retrieve_rerank_failure_returns_sanitized_deduplicated():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock(organization_id="org-1")
    db = MagicMock()
    db.get = AsyncMock(return_value=MagicMock(do_kb_uuid="kb-1"))
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)
    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="Call 415-555-0101", document_id="a.pdf"),
                Chunk(text="Call 415-555-0102", document_id="b.pdf"),
            ],
            total=2,
        )
    )

    async def _failure_passthrough(_query, chunks):
        assert [chunk.text for chunk in chunks] == ["Call <phone>"]
        return chunks

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
        patch(
            "src.services.do_kb.rerank.cohere_rescore_chunks",
            AsyncMock(side_effect=_failure_passthrough),
        ),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    assert [chunk["text"] for chunk in result["chunks"]] == ["Call <phone>"]


@pytest.mark.unit
async def test_tool_do_kb_retrieve_empty_after_sanitization_returns_safe_reason():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
    from src.services.do_kb.models import RetrieveResult

    user = MagicMock(organization_id="org-1")
    db = MagicMock()
    db.get = AsyncMock(return_value=MagicMock(do_kb_uuid="kb-1"))
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)
    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text=" \n ", document_id="a.pdf")],
            total=1,
        )
    )
    rerank = AsyncMock()

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
        patch("src.services.do_kb.rerank.cohere_rescore_chunks", rerank),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    assert result["chunks"] == []
    assert result["total"] == 0
    assert result["reason"] == "no_safe_chunks"
    rerank.assert_not_awaited()


# -- Call-site wiring: evidence_mode / summarize_evidence (PR-2) -------------


@pytest.mark.unit
async def test_tool_do_kb_retrieve_evidence_flag_on_calls_summarize_evidence():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
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
            "score_source": None,
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
            "score_source": None,
            "document_id": "a.pdf",
            "title": "a.pdf",
            "metadata": {},
        }
    ]
    assert result["evidence_mode"] is True
    assert result["chunks"] == enriched_payload


@pytest.mark.unit
async def test_tool_do_kb_retrieve_evidence_flag_off_never_calls_summarize_evidence():
    from src.services.agent.tools_impl import _tool_do_kb_retrieve
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
