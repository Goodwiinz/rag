from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.research.chat import (
    RetrievedContext,
    _background_evaluate_rag,
    retrieve_context,
)
from src.models.search_schemas import SearchResponse, SearchResult, SearchType
from src.services.diagnostics.retrieval_diagnostics import RetrievalTrace


pytestmark = pytest.mark.asyncio


@patch("src.services.diagnostics.diagnostics_store.diagnostics_store.store_trace", new_callable=AsyncMock)
@patch("src.api.research.chat.hybrid_search_service.search_with_diagnostics")
async def test_retrieve_context_prefers_full_text_metadata(
    mock_search_with_diagnostics: MagicMock,
    _mock_store_trace: AsyncMock,
) -> None:
    full_chunk_text = "A" * 1200
    result = SearchResult(
        document_id="doc-1",
        title="Doc 1",
        document_type="text",
        content_preview="preview-only",
        snippets=[],
        relevance_score=0.95,
        file_size_bytes=100,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        processing_status="completed",
        tags=[],
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
        metadata={"full_text": full_chunk_text, "source": "vector"},
    )
    mock_search_with_diagnostics.return_value = (
        SearchResponse(
            query="q",
            search_id="sid",
            search_type=SearchType.HYBRID,
            results=[result],
            total_results=1,
            returned_results=1,
            search_time_ms=1.0,
            limit=1,
            offset=0,
            has_more=False,
            suggestions=[],
        ),
        RetrievalTrace(query="q"),
    )

    contexts, _trace_id = await retrieve_context("q", max_docs=1)

    assert len(contexts) == 1
    assert contexts[0].content == full_chunk_text


@patch(
    "src.services.diagnostics.diagnostics_store.diagnostics_store.update_trace_evaluation",
    new_callable=AsyncMock,
)
@patch(
    "src.services.evaluation.rag_evaluation_service.rag_evaluation_service.run_rag_triad_evaluation",
    new_callable=AsyncMock,
)
@patch("src.core.database.get_db_sync")
async def test_background_evaluate_rag_uses_sync_db_session(
    mock_get_db_sync: MagicMock,
    mock_run_evaluation: AsyncMock,
    mock_update_trace_evaluation: AsyncMock,
) -> None:
    db = MagicMock()
    mock_get_db_sync.return_value = iter([db])
    mock_run_evaluation.return_value = MagicMock(
        answer_relevancy=0.91,
        faithfulness=0.89,
        contextual_relevancy=0.87,
        overall_score=0.89,
        hallucination_rate=0.03,
    )
    contexts = [
        RetrievedContext(
            document_id="doc-1",
            title="Doc 1",
            content="Some context",
            score=0.95,
            source="vector",
        )
    ]

    await _background_evaluate_rag(
        query="What is RAG?",
        answer="RAG combines retrieval and generation.",
        contexts=contexts,
        trace_id="trace-123",
    )

    mock_run_evaluation.assert_awaited_once()
    mock_update_trace_evaluation.assert_awaited_once()
    db.close.assert_called_once()
