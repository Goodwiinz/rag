"""Unit tests for retrieval diagnostics data model.

Tests cover:
- Dataclass creation and field defaults
- to_dict() serialization for all dataclasses
- from_dict() deserialization (round-trip preservation)
- RetrievalTrace with all pipeline stages populated
- Edge cases: empty lists, None values, missing optional fields
"""

import uuid
from copy import deepcopy

import pytest

from src.services.diagnostics.retrieval_diagnostics import (
    ContextDiagnostics,
    FusionDiagnostics,
    RerankDiagnostics,
    RetrievalTrace,
    SourceDiagnostics,
)


# ============================================================================
# Factories
# ============================================================================


def _make_source_diagnostics(**overrides) -> SourceDiagnostics:
    """Factory for SourceDiagnostics with sensible defaults."""
    defaults = {
        "source_type": "fulltext",
        "search_time_ms": 42.5,
        "result_count": 10,
        "total_available": 100,
        "success": True,
        "error": None,
        "top_scores": [0.95, 0.88, 0.72],
        "avg_score": 0.85,
    }
    defaults.update(overrides)
    return SourceDiagnostics(**defaults)


def _make_fusion_diagnostics(**overrides) -> FusionDiagnostics:
    """Factory for FusionDiagnostics with sensible defaults."""
    defaults = {
        "input_count": 30,
        "output_count": 18,
        "multi_source_count": 5,
        "weights_used": {"fulltext": 0.4, "vector": 0.4, "knowledge_graph": 0.2},
        "score_distribution": {"min": 0.1, "max": 0.95, "mean": 0.55, "median": 0.52},
        "fusion_time_ms": 3.2,
    }
    defaults.update(overrides)
    return FusionDiagnostics(**defaults)


def _make_rerank_diagnostics(**overrides) -> RerankDiagnostics:
    """Factory for RerankDiagnostics with sensible defaults."""
    defaults = {
        "enabled": True,
        "rerank_time_ms": 150.0,
        "input_count": 18,
        "output_count": 10,
        "score_deltas": [
            {"doc_id": "doc-1", "before": 0.8, "after": 0.95, "delta": 0.15},
            {"doc_id": "doc-2", "before": 0.7, "after": 0.6, "delta": -0.1},
        ],
        "fallback_used": False,
        "error": None,
    }
    defaults.update(overrides)
    return RerankDiagnostics(**defaults)


def _make_context_diagnostics(**overrides) -> ContextDiagnostics:
    """Factory for ContextDiagnostics with sensible defaults."""
    defaults = {
        "docs_retrieved": 5,
        "docs_with_content": 4,
        "total_chars_before_truncation": 10000,
        "total_chars_after_truncation": 8000,
        "truncated_docs": [
            {"doc_id": "doc-3", "before": 3000, "after": 2000},
        ],
        "truncation_ratio": 0.20,
        "char_limit": 3000,
    }
    defaults.update(overrides)
    return ContextDiagnostics(**defaults)


def _make_retrieval_trace(**overrides) -> RetrievalTrace:
    """Factory for a fully-populated RetrievalTrace."""
    defaults = {
        "trace_id": str(uuid.uuid4()),
        "query": "What is machine learning?",
        "timestamp": "2026-02-17T12:00:00+00:00",
        "total_time_ms": 250.0,
        "sources": [
            _make_source_diagnostics(source_type="fulltext"),
            _make_source_diagnostics(source_type="vector", search_time_ms=80.0),
        ],
        "fusion": _make_fusion_diagnostics(),
        "rerank": _make_rerank_diagnostics(),
        "context": _make_context_diagnostics(),
        "final_result_count": 5,
        "search_type": "hybrid",
        "evaluation_id": "eval-abc",
        "evaluation_scores": {"precision_at_3": 0.8, "mrr": 0.9},
    }
    defaults.update(overrides)
    return RetrievalTrace(**defaults)


# ============================================================================
# SourceDiagnostics Tests
# ============================================================================


class TestSourceDiagnostics:
    """Tests for SourceDiagnostics dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """SourceDiagnostics should accept and store all fields."""
        src = _make_source_diagnostics()
        assert src.source_type == "fulltext"
        assert src.search_time_ms == 42.5
        assert src.result_count == 10
        assert src.total_available == 100
        assert src.success is True
        assert src.error is None
        assert src.top_scores == [0.95, 0.88, 0.72]
        assert src.avg_score == 0.85

    def test_defaults(self) -> None:
        """Optional fields should use correct defaults."""
        src = SourceDiagnostics(
            source_type="vector",
            search_time_ms=10.0,
            result_count=0,
            total_available=0,
            success=False,
            error="timeout",
        )
        assert src.top_scores == []
        assert src.avg_score == 0.0

    def test_to_dict(self) -> None:
        """to_dict() should return a complete dictionary representation."""
        src = _make_source_diagnostics()
        d = src.to_dict()

        assert isinstance(d, dict)
        assert d["source_type"] == "fulltext"
        assert d["search_time_ms"] == 42.5
        assert d["result_count"] == 10
        assert d["total_available"] == 100
        assert d["success"] is True
        assert d["error"] is None
        assert d["top_scores"] == [0.95, 0.88, 0.72]
        assert d["avg_score"] == 0.85

    def test_round_trip(self) -> None:
        """to_dict() -> from_dict() should preserve all fields."""
        original = _make_source_diagnostics()
        restored = SourceDiagnostics.from_dict(original.to_dict())

        assert restored.source_type == original.source_type
        assert restored.search_time_ms == original.search_time_ms
        assert restored.result_count == original.result_count
        assert restored.total_available == original.total_available
        assert restored.success == original.success
        assert restored.error == original.error
        assert restored.top_scores == original.top_scores
        assert restored.avg_score == original.avg_score

    def test_round_trip_with_error(self) -> None:
        """Round-trip should preserve error string."""
        original = _make_source_diagnostics(success=False, error="Connection refused")
        restored = SourceDiagnostics.from_dict(original.to_dict())
        assert restored.success is False
        assert restored.error == "Connection refused"

    def test_from_dict_ignores_unknown_keys(self) -> None:
        """from_dict() should silently ignore keys not in the dataclass."""
        d = _make_source_diagnostics().to_dict()
        d["extra_field"] = "should be ignored"
        restored = SourceDiagnostics.from_dict(d)
        assert not hasattr(restored, "extra_field")


# ============================================================================
# FusionDiagnostics Tests
# ============================================================================


class TestFusionDiagnostics:
    """Tests for FusionDiagnostics dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """FusionDiagnostics should accept and store all fields."""
        fusion = _make_fusion_diagnostics()
        assert fusion.input_count == 30
        assert fusion.output_count == 18
        assert fusion.multi_source_count == 5
        assert fusion.weights_used["fulltext"] == 0.4
        assert fusion.score_distribution["mean"] == 0.55
        assert fusion.fusion_time_ms == 3.2

    def test_defaults(self) -> None:
        """Default values should be empty dicts and 0.0 for time."""
        fusion = FusionDiagnostics(input_count=0, output_count=0, multi_source_count=0)
        assert fusion.weights_used == {}
        assert fusion.score_distribution == {}
        assert fusion.fusion_time_ms == 0.0

    def test_to_dict(self) -> None:
        """to_dict() should produce a correct dictionary."""
        fusion = _make_fusion_diagnostics()
        d = fusion.to_dict()

        assert d["input_count"] == 30
        assert d["output_count"] == 18
        assert d["multi_source_count"] == 5
        assert "fulltext" in d["weights_used"]
        assert "min" in d["score_distribution"]

    def test_round_trip(self) -> None:
        """to_dict() -> from_dict() should preserve all fields."""
        original = _make_fusion_diagnostics()
        restored = FusionDiagnostics.from_dict(original.to_dict())

        assert restored.input_count == original.input_count
        assert restored.output_count == original.output_count
        assert restored.multi_source_count == original.multi_source_count
        assert restored.weights_used == original.weights_used
        assert restored.score_distribution == original.score_distribution
        assert restored.fusion_time_ms == original.fusion_time_ms


# ============================================================================
# RerankDiagnostics Tests
# ============================================================================


class TestRerankDiagnostics:
    """Tests for RerankDiagnostics dataclass."""

    def test_creation_enabled(self) -> None:
        """RerankDiagnostics with reranking enabled should store all fields."""
        rerank = _make_rerank_diagnostics()
        assert rerank.enabled is True
        assert rerank.rerank_time_ms == 150.0
        assert rerank.input_count == 18
        assert rerank.output_count == 10
        assert len(rerank.score_deltas) == 2
        assert rerank.fallback_used is False
        assert rerank.error is None

    def test_creation_disabled(self) -> None:
        """RerankDiagnostics with reranking disabled should use defaults."""
        rerank = RerankDiagnostics(enabled=False)
        assert rerank.enabled is False
        assert rerank.rerank_time_ms == 0.0
        assert rerank.input_count == 0
        assert rerank.output_count == 0
        assert rerank.score_deltas == []
        assert rerank.fallback_used is False
        assert rerank.error is None

    def test_creation_with_fallback(self) -> None:
        """RerankDiagnostics with fallback should capture error."""
        rerank = _make_rerank_diagnostics(
            fallback_used=True, error="Cohere API timeout"
        )
        assert rerank.fallback_used is True
        assert rerank.error == "Cohere API timeout"

    def test_to_dict(self) -> None:
        """to_dict() should produce a correct dictionary."""
        rerank = _make_rerank_diagnostics()
        d = rerank.to_dict()

        assert d["enabled"] is True
        assert d["rerank_time_ms"] == 150.0
        assert len(d["score_deltas"]) == 2
        assert d["score_deltas"][0]["doc_id"] == "doc-1"

    def test_round_trip(self) -> None:
        """to_dict() -> from_dict() should preserve all fields."""
        original = _make_rerank_diagnostics()
        restored = RerankDiagnostics.from_dict(original.to_dict())

        assert restored.enabled == original.enabled
        assert restored.rerank_time_ms == original.rerank_time_ms
        assert restored.input_count == original.input_count
        assert restored.output_count == original.output_count
        assert restored.score_deltas == original.score_deltas
        assert restored.fallback_used == original.fallback_used
        assert restored.error == original.error

    def test_round_trip_fallback(self) -> None:
        """Round-trip with fallback_used=True should preserve error."""
        original = _make_rerank_diagnostics(
            fallback_used=True, error="API key invalid"
        )
        restored = RerankDiagnostics.from_dict(original.to_dict())
        assert restored.fallback_used is True
        assert restored.error == "API key invalid"


# ============================================================================
# ContextDiagnostics Tests
# ============================================================================


class TestContextDiagnostics:
    """Tests for ContextDiagnostics dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """ContextDiagnostics should accept and store all fields."""
        ctx = _make_context_diagnostics()
        assert ctx.docs_retrieved == 5
        assert ctx.docs_with_content == 4
        assert ctx.total_chars_before_truncation == 10000
        assert ctx.total_chars_after_truncation == 8000
        assert len(ctx.truncated_docs) == 1
        assert ctx.truncation_ratio == 0.20
        assert ctx.char_limit == 3000

    def test_defaults(self) -> None:
        """Default truncated_docs should be empty list, default ratio 0.0."""
        ctx = ContextDiagnostics(
            docs_retrieved=3,
            docs_with_content=3,
            total_chars_before_truncation=5000,
            total_chars_after_truncation=5000,
        )
        assert ctx.truncated_docs == []
        assert ctx.truncation_ratio == 0.0
        assert ctx.char_limit == 3000

    def test_to_dict(self) -> None:
        """to_dict() should produce a correct dictionary."""
        ctx = _make_context_diagnostics()
        d = ctx.to_dict()

        assert d["docs_retrieved"] == 5
        assert d["docs_with_content"] == 4
        assert d["total_chars_before_truncation"] == 10000
        assert d["total_chars_after_truncation"] == 8000
        assert d["truncated_docs"][0]["doc_id"] == "doc-3"
        assert d["truncation_ratio"] == 0.20
        assert d["char_limit"] == 3000

    def test_round_trip(self) -> None:
        """to_dict() -> from_dict() should preserve all fields."""
        original = _make_context_diagnostics()
        restored = ContextDiagnostics.from_dict(original.to_dict())

        assert restored.docs_retrieved == original.docs_retrieved
        assert restored.docs_with_content == original.docs_with_content
        assert restored.total_chars_before_truncation == original.total_chars_before_truncation
        assert restored.total_chars_after_truncation == original.total_chars_after_truncation
        assert restored.truncated_docs == original.truncated_docs
        assert restored.truncation_ratio == original.truncation_ratio
        assert restored.char_limit == original.char_limit


# ============================================================================
# RetrievalTrace Tests
# ============================================================================


class TestRetrievalTrace:
    """Tests for RetrievalTrace dataclass."""

    def test_creation_with_all_stages(self) -> None:
        """RetrievalTrace should store all pipeline stages."""
        trace = _make_retrieval_trace()

        assert trace.query == "What is machine learning?"
        assert trace.total_time_ms == 250.0
        assert len(trace.sources) == 2
        assert trace.fusion is not None
        assert trace.rerank is not None
        assert trace.context is not None
        assert trace.final_result_count == 5
        assert trace.search_type == "hybrid"
        assert trace.evaluation_id == "eval-abc"
        assert trace.evaluation_scores == {"precision_at_3": 0.8, "mrr": 0.9}

    def test_defaults(self) -> None:
        """Default RetrievalTrace should have empty lists and None optionals."""
        trace = RetrievalTrace()

        assert isinstance(trace.trace_id, str)
        assert len(trace.trace_id) > 0  # UUID was generated
        assert trace.query == ""
        assert trace.timestamp != ""  # Timestamp was auto-generated
        assert trace.total_time_ms == 0.0
        assert trace.sources == []
        assert trace.fusion is None
        assert trace.rerank is None
        assert trace.context is None
        assert trace.final_result_count == 0
        assert trace.search_type == "hybrid"
        assert trace.evaluation_id is None
        assert trace.evaluation_scores is None

    def test_auto_generated_trace_id(self) -> None:
        """Two default traces should have different trace_ids."""
        trace1 = RetrievalTrace()
        trace2 = RetrievalTrace()
        assert trace1.trace_id != trace2.trace_id

    def test_auto_generated_timestamp(self) -> None:
        """Default timestamp should be a valid ISO-format string."""
        trace = RetrievalTrace()
        from datetime import datetime

        # Should not raise
        datetime.fromisoformat(trace.timestamp)

    def test_to_dict_full(self) -> None:
        """to_dict() with all stages should produce a complete dict."""
        trace = _make_retrieval_trace()
        d = trace.to_dict()

        assert d["trace_id"] == trace.trace_id
        assert d["query"] == "What is machine learning?"
        assert d["total_time_ms"] == 250.0
        assert len(d["sources"]) == 2
        assert d["sources"][0]["source_type"] == "fulltext"
        assert d["sources"][1]["source_type"] == "vector"
        assert d["fusion"] is not None
        assert d["fusion"]["input_count"] == 30
        assert d["rerank"] is not None
        assert d["rerank"]["enabled"] is True
        assert d["context"] is not None
        assert d["context"]["docs_retrieved"] == 5
        assert d["final_result_count"] == 5
        assert d["search_type"] == "hybrid"
        assert d["evaluation_id"] == "eval-abc"
        assert d["evaluation_scores"]["precision_at_3"] == 0.8

    def test_to_dict_minimal(self) -> None:
        """to_dict() with no stages should have None for optional stages."""
        trace = RetrievalTrace(query="test")
        d = trace.to_dict()

        assert d["query"] == "test"
        assert d["sources"] == []
        assert d["fusion"] is None
        assert d["rerank"] is None
        assert d["context"] is None

    def test_round_trip_full(self) -> None:
        """Full round-trip: to_dict() -> from_dict() should preserve every field."""
        original = _make_retrieval_trace()
        d = original.to_dict()
        restored = RetrievalTrace.from_dict(d)

        assert restored.trace_id == original.trace_id
        assert restored.query == original.query
        assert restored.timestamp == original.timestamp
        assert restored.total_time_ms == original.total_time_ms
        assert len(restored.sources) == len(original.sources)
        assert restored.sources[0].source_type == original.sources[0].source_type
        assert restored.sources[1].search_time_ms == original.sources[1].search_time_ms
        assert restored.fusion.input_count == original.fusion.input_count
        assert restored.rerank.enabled == original.rerank.enabled
        assert restored.rerank.score_deltas == original.rerank.score_deltas
        assert restored.context.truncation_ratio == original.context.truncation_ratio
        assert restored.final_result_count == original.final_result_count
        assert restored.search_type == original.search_type
        assert restored.evaluation_id == original.evaluation_id
        assert restored.evaluation_scores == original.evaluation_scores

    def test_round_trip_minimal(self) -> None:
        """Round-trip with minimal trace should preserve defaults."""
        original = RetrievalTrace(query="hello")
        d = original.to_dict()
        restored = RetrievalTrace.from_dict(d)

        assert restored.query == "hello"
        assert restored.sources == []
        assert restored.fusion is None
        assert restored.rerank is None
        assert restored.context is None

    def test_from_dict_missing_optional_fields(self) -> None:
        """from_dict() with missing optional fields should use defaults."""
        d = {"trace_id": "test-123", "query": "test query"}
        restored = RetrievalTrace.from_dict(d)

        assert restored.trace_id == "test-123"
        assert restored.query == "test query"
        assert restored.timestamp == ""
        assert restored.total_time_ms == 0.0
        assert restored.sources == []
        assert restored.fusion is None
        assert restored.evaluation_id is None

    def test_from_dict_generates_trace_id_when_missing(self) -> None:
        """from_dict() with no trace_id should generate a UUID."""
        d = {"query": "test query"}
        restored = RetrievalTrace.from_dict(d)

        assert restored.trace_id is not None
        assert len(restored.trace_id) > 0
        # Should be a valid UUID
        uuid.UUID(restored.trace_id)

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict() output should be fully JSON-serializable."""
        import json

        trace = _make_retrieval_trace()
        d = trace.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        assert deserialized["trace_id"] == trace.trace_id
