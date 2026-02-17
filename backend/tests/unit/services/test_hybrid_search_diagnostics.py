"""Unit tests for HybridSearchService.search_with_diagnostics().

Tests cover:
- Return value shape (SearchResponse, RetrievalTrace)
- SourceDiagnostics population per source
- FusionDiagnostics capture of weights, input/output counts, multi-source counts
- RerankDiagnostics score deltas when reranking is enabled
- weights_override temporary application and restoration
- Error handling returning fallback response with partial trace
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.models.search_schemas import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
)
from src.services.diagnostics.retrieval_diagnostics import (
    FusionDiagnostics,
    RerankDiagnostics,
    RetrievalTrace,
    SourceDiagnostics,
)
from src.services.search.hybrid_search_service import (
    HybridSearchService,
    RawSearchResult,
    SearchSourceResult,
    SearchSourceType,
)


# ============================================================================
# Factories
# ============================================================================


def _make_search_request(**overrides) -> SearchQuery:
    """Factory for SearchQuery with sensible defaults."""
    defaults = {
        "query": "What is machine learning?",
        "search_type": SearchType.HYBRID,
        "limit": 5,
        "offset": 0,
    }
    defaults.update(overrides)
    return SearchQuery(**defaults)


def _make_search_result(document_id: str = "doc-1", score: float = 0.85) -> SearchResult:
    """Factory for a SearchResult."""
    return SearchResult(
        document_id=document_id,
        title=f"Title for {document_id}",
        document_type="text",
        content_preview="Some preview content",
        snippets=[],
        relevance_score=score,
        file_size_bytes=1024,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        processing_status="completed",
        tags=[],
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
        metadata={},
    )


def _make_raw_result(
    document_id: str = "doc-1",
    source: SearchSourceType = SearchSourceType.FULLTEXT,
    score: float = 0.85,
) -> RawSearchResult:
    """Factory for a RawSearchResult."""
    return RawSearchResult(
        document_id=document_id,
        source_type=source,
        relevance_score=score,
        metadata={"original_score": score, "source": source.value},
        search_result=_make_search_result(document_id, score),
    )


def _make_source_result(
    source_type: SearchSourceType = SearchSourceType.FULLTEXT,
    results: list = None,
    search_time_ms: float = 50.0,
    success: bool = True,
    error: str = None,
) -> SearchSourceResult:
    """Factory for SearchSourceResult."""
    if results is None:
        results = [
            _make_raw_result(f"doc-{i}", source_type, 0.9 - i * 0.1)
            for i in range(3)
        ]
    return SearchSourceResult(
        source_type=source_type,
        results=results,
        search_time_ms=search_time_ms,
        total_available=len(results) * 3,
        success=success,
        error=error,
    )


# ============================================================================
# Service Setup Helper
# ============================================================================


def _create_service_with_mocks(
    source_results=None,
    fused_results=None,
    reranked_results=None,
    reranking_enabled=False,
    final_results=None,
):
    """Create a HybridSearchService with internal methods mocked.

    Returns (service, mock_dict) where mock_dict holds all patch references.
    """
    service = HybridSearchService()

    # Default source results: fulltext and vector
    if source_results is None:
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(SearchSourceType.FULLTEXT),
            SearchSourceType.VECTOR: _make_source_result(SearchSourceType.VECTOR),
        }

    # Default fused results
    if fused_results is None:
        fused_results = [
            _make_raw_result("doc-0", SearchSourceType.FULLTEXT, 0.9),
            _make_raw_result("doc-1", SearchSourceType.FULLTEXT, 0.8),
            _make_raw_result("doc-2", SearchSourceType.FULLTEXT, 0.7),
        ]

    # Default reranked results (same as fused but with updated scores)
    if reranked_results is None:
        reranked_results = [
            _make_raw_result("doc-1", SearchSourceType.FULLTEXT, 0.95),
            _make_raw_result("doc-0", SearchSourceType.FULLTEXT, 0.85),
            _make_raw_result("doc-2", SearchSourceType.FULLTEXT, 0.6),
        ]

    # Default final results
    if final_results is None:
        final_results = [
            _make_search_result("doc-0", 0.9),
            _make_search_result("doc-1", 0.8),
        ]

    service._route_search_query = MagicMock(return_value=list(source_results.keys()))
    service._execute_parallel_searches = MagicMock(return_value=source_results)
    service._fuse_search_results = MagicMock(return_value=fused_results)
    service._apply_cohere_reranking = MagicMock(return_value=reranked_results)
    service._apply_final_filtering = MagicMock(return_value=final_results)
    service._get_hybrid_suggestions = MagicMock(return_value=[])

    mocks = {
        "route": service._route_search_query,
        "parallel": service._execute_parallel_searches,
        "fuse": service._fuse_search_results,
        "rerank_apply": service._apply_cohere_reranking,
        "filter": service._apply_final_filtering,
        "suggestions": service._get_hybrid_suggestions,
    }

    return service, mocks


# ============================================================================
# Return Type Tests
# ============================================================================


class TestSearchWithDiagnosticsReturnType:
    """Tests for the return value shape of search_with_diagnostics()."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_returns_tuple_of_response_and_trace(self, mock_cohere) -> None:
        """search_with_diagnostics() should return (SearchResponse, RetrievalTrace)."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        result = service.search_with_diagnostics(search_request=request)

        assert isinstance(result, tuple)
        assert len(result) == 2
        response, trace = result
        assert isinstance(response, SearchResponse)
        assert isinstance(trace, RetrievalTrace)

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_response_has_correct_query(self, mock_cohere) -> None:
        """The SearchResponse should contain the original query."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request(query="test query")

        response, trace = service.search_with_diagnostics(search_request=request)

        assert response.query == "test query"
        assert trace.query == "test query"

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_trace_has_search_type(self, mock_cohere) -> None:
        """The trace search_type should reflect the request."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.search_type == "hybrid"


# ============================================================================
# Source Diagnostics Tests
# ============================================================================


class TestSourceDiagnosticsPopulation:
    """Tests for SourceDiagnostics being populated per source."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_sources_populated_per_source(self, mock_cohere) -> None:
        """Each source in source_results should produce a SourceDiagnostics entry."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, search_time_ms=30.0
            ),
            SearchSourceType.VECTOR: _make_source_result(
                SearchSourceType.VECTOR, search_time_ms=60.0
            ),
            SearchSourceType.KNOWLEDGE_GRAPH: _make_source_result(
                SearchSourceType.KNOWLEDGE_GRAPH, search_time_ms=45.0
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert len(trace.sources) == 3
        source_types = {s.source_type for s in trace.sources}
        assert source_types == {"fulltext", "vector", "knowledge_graph"}

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_source_timing_captured(self, mock_cohere) -> None:
        """Each SourceDiagnostics should capture search_time_ms from the source result."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, search_time_ms=42.0
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.sources[0].search_time_ms == 42.0

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_source_result_count_and_available(self, mock_cohere) -> None:
        """SourceDiagnostics should capture result_count and total_available."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        raw_results = [
            _make_raw_result(f"doc-{i}", SearchSourceType.FULLTEXT, 0.9 - i * 0.1)
            for i in range(5)
        ]
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, results=raw_results
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.sources[0].result_count == 5
        assert trace.sources[0].total_available == 15  # len * 3 from factory

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_source_success_and_error(self, mock_cohere) -> None:
        """Failed sources should have success=False and an error message."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, success=True
            ),
            SearchSourceType.VECTOR: _make_source_result(
                SearchSourceType.VECTOR,
                results=[],
                success=False,
                error="Connection timeout",
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        fulltext_src = next(s for s in trace.sources if s.source_type == "fulltext")
        vector_src = next(s for s in trace.sources if s.source_type == "vector")
        assert fulltext_src.success is True
        assert fulltext_src.error is None
        assert vector_src.success is False
        assert vector_src.error == "Connection timeout"

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_source_top_scores_and_avg(self, mock_cohere) -> None:
        """SourceDiagnostics should capture top scores and average score."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        raw_results = [
            _make_raw_result("doc-0", SearchSourceType.FULLTEXT, 0.9),
            _make_raw_result("doc-1", SearchSourceType.FULLTEXT, 0.7),
        ]
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, results=raw_results
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        src = trace.sources[0]
        assert src.top_scores == [0.9, 0.7]  # sorted desc, top 5
        assert src.avg_score == pytest.approx(0.8, abs=0.01)


# ============================================================================
# Fusion Diagnostics Tests
# ============================================================================


class TestFusionDiagnostics:
    """Tests for FusionDiagnostics population."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_fusion_weights_captured(self, mock_cohere) -> None:
        """FusionDiagnostics should capture the weights used for fusion."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.fusion is not None
        assert trace.fusion.weights_used["fulltext"] == 0.4
        assert trace.fusion.weights_used["vector"] == 0.4
        assert trace.fusion.weights_used["knowledge_graph"] == 0.2

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_fusion_input_output_counts(self, mock_cohere) -> None:
        """FusionDiagnostics should capture raw input and unique output counts."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        # 3 results per source, 2 sources = 6 raw inputs
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(SearchSourceType.FULLTEXT),
            SearchSourceType.VECTOR: _make_source_result(SearchSourceType.VECTOR),
        }
        fused_results = [
            _make_raw_result("doc-0", score=0.9),
            _make_raw_result("doc-1", score=0.8),
            _make_raw_result("doc-2", score=0.7),
            _make_raw_result("doc-3", score=0.6),
        ]
        service, _ = _create_service_with_mocks(
            source_results=source_results, fused_results=fused_results
        )
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.fusion.input_count == 6  # 3 per source * 2 sources
        assert trace.fusion.output_count == 4  # 4 fused results

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_fusion_multi_source_count(self, mock_cohere) -> None:
        """FusionDiagnostics should count documents appearing in multiple sources."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        # doc-0 appears in both sources
        ft_results = [
            _make_raw_result("doc-0", SearchSourceType.FULLTEXT, 0.9),
            _make_raw_result("doc-1", SearchSourceType.FULLTEXT, 0.8),
        ]
        vec_results = [
            _make_raw_result("doc-0", SearchSourceType.VECTOR, 0.85),
            _make_raw_result("doc-2", SearchSourceType.VECTOR, 0.7),
        ]
        source_results = {
            SearchSourceType.FULLTEXT: _make_source_result(
                SearchSourceType.FULLTEXT, results=ft_results
            ),
            SearchSourceType.VECTOR: _make_source_result(
                SearchSourceType.VECTOR, results=vec_results
            ),
        }
        service, _ = _create_service_with_mocks(source_results=source_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.fusion.multi_source_count == 1  # only doc-0

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_fusion_score_distribution(self, mock_cohere) -> None:
        """FusionDiagnostics should capture score distribution stats."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        fused_results = [
            _make_raw_result("doc-0", score=0.9),
            _make_raw_result("doc-1", score=0.5),
            _make_raw_result("doc-2", score=0.3),
        ]
        service, _ = _create_service_with_mocks(fused_results=fused_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        dist = trace.fusion.score_distribution
        assert "min" in dist
        assert "max" in dist
        assert "mean" in dist
        assert "median" in dist
        assert dist["min"] == pytest.approx(0.3, abs=0.01)
        assert dist["max"] == pytest.approx(0.9, abs=0.01)


# ============================================================================
# Rerank Diagnostics Tests
# ============================================================================


class TestRerankDiagnostics:
    """Tests for RerankDiagnostics population."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_rerank_disabled(self, mock_cohere) -> None:
        """When reranking is disabled, rerank diagnostics should show enabled=False."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.rerank is not None
        assert trace.rerank.enabled is False

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_rerank_enabled_captures_deltas(self, mock_cohere) -> None:
        """When reranking is enabled, score deltas should be captured."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=True)

        # Fused results with known scores
        fused_results = [
            _make_raw_result("doc-0", score=0.8),
            _make_raw_result("doc-1", score=0.7),
        ]
        # Reranked results with new scores
        reranked = [
            _make_raw_result("doc-1", score=0.95),
            _make_raw_result("doc-0", score=0.6),
        ]
        service, _ = _create_service_with_mocks(
            fused_results=fused_results, reranked_results=reranked
        )
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.rerank is not None
        assert trace.rerank.enabled is True
        assert trace.rerank.input_count == 2
        assert trace.rerank.output_count == 2
        assert trace.rerank.fallback_used is False
        assert len(trace.rerank.score_deltas) == 2

        # Verify deltas are computed
        for delta in trace.rerank.score_deltas:
            assert "doc_id" in delta
            assert "before" in delta
            assert "after" in delta
            assert "delta" in delta

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_rerank_fallback_on_error(self, mock_cohere) -> None:
        """When reranking raises, fallback_used should be True with error."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=True)

        service, mocks = _create_service_with_mocks()
        mocks["rerank_apply"].side_effect = RuntimeError("Cohere API failure")
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.rerank is not None
        assert trace.rerank.enabled is True
        assert trace.rerank.fallback_used is True
        assert "Cohere API failure" in trace.rerank.error

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_rerank_not_applied_when_no_fused_results(self, mock_cohere) -> None:
        """When fused results are empty, reranking should be skipped."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=True)

        service, mocks = _create_service_with_mocks(fused_results=[])
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        # Reranking should be disabled since there are no results
        assert trace.rerank is not None
        assert trace.rerank.enabled is False
        mocks["rerank_apply"].assert_not_called()


# ============================================================================
# Weights Override Tests
# ============================================================================


class TestWeightsOverride:
    """Tests for weights_override parameter."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_weights_override_applied(self, mock_cohere) -> None:
        """weights_override should affect only per-request fusion weights."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()
        original_ft = service.fulltext_weight
        original_vec = service.vector_weight
        original_kg = service.knowledge_graph_weight

        override = {"fulltext": 0.6, "vector": 0.3, "knowledge_graph": 0.1}
        _, trace = service.search_with_diagnostics(
            search_request=request, weights_override=override
        )

        # Fusion diagnostics should reflect the overridden weights
        assert trace.fusion.weights_used["fulltext"] == 0.6
        assert trace.fusion.weights_used["vector"] == 0.3
        assert trace.fusion.weights_used["knowledge_graph"] == 0.1
        assert service.fulltext_weight == original_ft
        assert service.vector_weight == original_vec
        assert service.knowledge_graph_weight == original_kg

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_weights_restored_after_override(self, mock_cohere) -> None:
        """Original weights should be restored after search_with_diagnostics() returns."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        original_ft = service.fulltext_weight
        original_vec = service.vector_weight
        original_kg = service.knowledge_graph_weight

        override = {"fulltext": 0.1, "vector": 0.8, "knowledge_graph": 0.1}
        service.search_with_diagnostics(
            search_request=request, weights_override=override
        )

        assert service.fulltext_weight == original_ft
        assert service.vector_weight == original_vec
        assert service.knowledge_graph_weight == original_kg

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_weights_restored_after_error(self, mock_cohere) -> None:
        """Weights should be restored even if an exception occurs during search."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, mocks = _create_service_with_mocks()
        # Force _route_search_query to raise
        mocks["route"].side_effect = RuntimeError("routing error")
        # Patch _fallback_to_fulltext to return a fallback response
        service._fallback_to_fulltext = MagicMock(
            return_value=SearchResponse(
                query="test",
                search_id="fallback-id",
                search_type=SearchType.FULLTEXT,
                results=[],
                total_results=0,
                returned_results=0,
                search_time_ms=0,
                limit=5,
                offset=0,
                has_more=False,
                suggestions=[],
            )
        )
        request = _make_search_request()

        original_ft = service.fulltext_weight
        original_vec = service.vector_weight

        override = {"fulltext": 0.1, "vector": 0.8, "knowledge_graph": 0.1}
        service.search_with_diagnostics(
            search_request=request, weights_override=override
        )

        assert service.fulltext_weight == original_ft
        assert service.vector_weight == original_vec

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_no_override_keeps_defaults(self, mock_cohere) -> None:
        """Without weights_override, default weights should be used."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.fusion.weights_used["fulltext"] == 0.4
        assert trace.fusion.weights_used["vector"] == 0.4
        assert trace.fusion.weights_used["knowledge_graph"] == 0.2


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in search_with_diagnostics()."""

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_error_returns_fallback_response_with_trace(self, mock_cohere) -> None:
        """On pipeline error, should return fallback response and partial trace."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, mocks = _create_service_with_mocks()
        mocks["route"].side_effect = RuntimeError("search routing failed")

        fallback_response = SearchResponse(
            query="test query",
            search_id="fallback-id",
            search_type=SearchType.FULLTEXT,
            results=[],
            total_results=0,
            returned_results=0,
            search_time_ms=0,
            limit=5,
            offset=0,
            has_more=False,
            suggestions=[],
        )
        service._fallback_to_fulltext = MagicMock(return_value=fallback_response)
        request = _make_search_request()

        response, trace = service.search_with_diagnostics(search_request=request)

        assert isinstance(response, SearchResponse)
        assert isinstance(trace, RetrievalTrace)
        assert trace.total_time_ms > 0  # Time was still recorded
        assert trace.query == "What is machine learning?"

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_trace_final_result_count(self, mock_cohere) -> None:
        """Trace should accurately report the final result count."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        final_results = [
            _make_search_result("doc-0", 0.9),
            _make_search_result("doc-1", 0.8),
            _make_search_result("doc-2", 0.7),
        ]
        service, _ = _create_service_with_mocks(final_results=final_results)
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.final_result_count == 3

    @patch("src.services.search.hybrid_search_service.cohere_rerank_service")
    def test_trace_total_time_is_positive(self, mock_cohere) -> None:
        """Trace total_time_ms should be a positive value."""
        type(mock_cohere).is_enabled = PropertyMock(return_value=False)
        service, _ = _create_service_with_mocks()
        request = _make_search_request()

        _, trace = service.search_with_diagnostics(search_request=request)

        assert trace.total_time_ms > 0
