"""Unit tests for diagnostics REST API endpoints.

Tests cover:
- GET /api/v1/diagnostics/traces/{trace_id} returns trace + bottleneck report
- GET /api/v1/diagnostics/traces/{trace_id} returns 404 for missing trace
- GET /api/v1/diagnostics/traces returns list of summaries
- GET /api/v1/diagnostics/aggregate returns stats
- POST /api/v1/diagnostics/weight-experiment validates weight sums
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.core.dependencies import require_admin
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


def _make_trace(**overrides) -> RetrievalTrace:
    """Factory for a RetrievalTrace with sensible defaults."""
    defaults = {
        "trace_id": "test-trace-001",
        "query": "What is machine learning?",
        "timestamp": "2026-02-17T12:00:00+00:00",
        "total_time_ms": 200.0,
        "sources": [
            SourceDiagnostics(
                source_type="fulltext",
                search_time_ms=50.0,
                result_count=5,
                total_available=20,
                success=True,
            ),
        ],
        "fusion": FusionDiagnostics(
            input_count=10, output_count=8, multi_source_count=3
        ),
        "rerank": RerankDiagnostics(enabled=True, rerank_time_ms=80.0),
        "context": ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=5000,
            total_chars_after_truncation=5000,
            truncation_ratio=0.0,
        ),
        "final_result_count": 5,
        "search_type": "hybrid",
    }
    defaults.update(overrides)
    return RetrievalTrace(**defaults)


@pytest.fixture(autouse=True)
def _override_diagnostics_auth(test_app, mock_admin_user):
    """Default diagnostics tests run as admin unless explicitly cleared."""
    test_app.dependency_overrides[require_admin] = lambda: mock_admin_user
    try:
        yield
    finally:
        test_app.dependency_overrides.pop(require_admin, None)


def test_diagnostics_requires_auth_without_override(test_app) -> None:
    """Diagnostics endpoints should reject unauthenticated requests."""
    test_app.dependency_overrides.pop(require_admin, None)

    with TestClient(test_app) as client:
        response = client.get("/api/v1/diagnostics/traces")

    assert response.status_code in (401, 403)


# ============================================================================
# GET /api/v1/diagnostics/traces/{trace_id}
# ============================================================================


class TestGetTraceEndpoint:
    """Tests for GET /api/v1/diagnostics/traces/{trace_id}."""

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_returns_trace_and_report(self, mock_store, test_client) -> None:
        """Should return the trace dict and a bottleneck_report."""
        trace = _make_trace()
        mock_store.get_trace = AsyncMock(return_value=trace)

        response = test_client.get("/api/v1/diagnostics/traces/test-trace-001")

        assert response.status_code == 200
        body = response.json()
        assert "trace" in body
        assert "bottleneck_report" in body
        assert body["trace"]["trace_id"] == "test-trace-001"
        assert body["trace"]["query"] == "What is machine learning?"

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_bottleneck_report_structure(self, mock_store, test_client) -> None:
        """Bottleneck report should have findings, stage_health, overall_health."""
        trace = _make_trace()
        mock_store.get_trace = AsyncMock(return_value=trace)

        response = test_client.get("/api/v1/diagnostics/traces/test-trace-001")

        report = response.json()["bottleneck_report"]
        assert "findings" in report
        assert "stage_health" in report
        assert "overall_health" in report
        assert isinstance(report["findings"], list)
        assert report["overall_health"] in ("green", "yellow", "red")

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_returns_404_for_missing_trace(self, mock_store, test_client) -> None:
        """Should return 404 when trace is not found."""
        mock_store.get_trace = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/diagnostics/traces/nonexistent")

        assert response.status_code == 404
        body = response.json()
        # The app wraps HTTP errors in {"error": {"message": ...}} format
        error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "not found" in error_msg.lower()

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_trace_sources_included(self, mock_store, test_client) -> None:
        """Response should include source diagnostics."""
        trace = _make_trace()
        mock_store.get_trace = AsyncMock(return_value=trace)

        response = test_client.get("/api/v1/diagnostics/traces/test-trace-001")

        sources = response.json()["trace"]["sources"]
        assert len(sources) == 1
        assert sources[0]["source_type"] == "fulltext"
        assert sources[0]["success"] is True


# ============================================================================
# GET /api/v1/diagnostics/traces
# ============================================================================


class TestGetRecentTracesEndpoint:
    """Tests for GET /api/v1/diagnostics/traces."""

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_returns_traces_list(self, mock_store, test_client) -> None:
        """Should return a list of trace summaries."""
        summaries = [
            {
                "trace_id": "t1",
                "query": "query 1",
                "timestamp": "2026-02-17T12:00:00+00:00",
                "total_time_ms": 100.0,
                "final_result_count": 5,
                "search_type": "hybrid",
                "source_count": 2,
                "has_evaluation": False,
            },
            {
                "trace_id": "t2",
                "query": "query 2",
                "timestamp": "2026-02-17T12:01:00+00:00",
                "total_time_ms": 150.0,
                "final_result_count": 3,
                "search_type": "hybrid",
                "source_count": 1,
                "has_evaluation": True,
            },
        ]
        mock_store.get_recent_traces = AsyncMock(return_value=summaries)

        response = test_client.get("/api/v1/diagnostics/traces")

        assert response.status_code == 200
        body = response.json()
        assert "traces" in body
        assert body["count"] == 2
        assert body["traces"][0]["trace_id"] == "t1"
        assert body["traces"][1]["trace_id"] == "t2"

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_supports_limit_and_offset(self, mock_store, test_client) -> None:
        """Should pass limit and offset query params to the store."""
        mock_store.get_recent_traces = AsyncMock(return_value=[])

        response = test_client.get(
            "/api/v1/diagnostics/traces?limit=10&offset=5"
        )

        assert response.status_code == 200
        mock_store.get_recent_traces.assert_called_once_with(limit=10, offset=5)
        body = response.json()
        assert body["limit"] == 10
        assert body["offset"] == 5

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_returns_empty_list(self, mock_store, test_client) -> None:
        """Should handle empty results gracefully."""
        mock_store.get_recent_traces = AsyncMock(return_value=[])

        response = test_client.get("/api/v1/diagnostics/traces")

        assert response.status_code == 200
        body = response.json()
        assert body["traces"] == []
        assert body["count"] == 0


# ============================================================================
# GET /api/v1/diagnostics/aggregate
# ============================================================================


class TestGetAggregateStatsEndpoint:
    """Tests for GET /api/v1/diagnostics/aggregate."""

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_returns_stats(self, mock_store, test_client) -> None:
        """Should return aggregate statistics."""
        stats = {
            "period_hours": 24,
            "total_traces": 100,
            "avg_time_ms": 180.5,
            "avg_result_count": 4.2,
            "source_stats": {
                "fulltext": {"avg_time_ms": 45.0, "max_time_ms": 120.0, "query_count": 100},
            },
            "source_failure_count": 2,
            "truncation_stats": {
                "avg_ratio": 0.1,
                "max_ratio": 0.35,
                "traces_with_truncation": 15,
            },
        }
        mock_store.get_aggregate_stats = AsyncMock(return_value=stats)

        response = test_client.get("/api/v1/diagnostics/aggregate")

        assert response.status_code == 200
        body = response.json()
        assert body["total_traces"] == 100
        assert body["avg_time_ms"] == 180.5
        assert "source_stats" in body

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_supports_hours_param(self, mock_store, test_client) -> None:
        """Should pass hours query param to the store."""
        mock_store.get_aggregate_stats = AsyncMock(
            return_value={"period_hours": 48, "total_traces": 0, "avg_time_ms": 0}
        )

        response = test_client.get("/api/v1/diagnostics/aggregate?hours=48")

        assert response.status_code == 200
        mock_store.get_aggregate_stats.assert_called_once_with(hours=48)


# ============================================================================
# POST /api/v1/diagnostics/weight-experiment
# ============================================================================


class TestWeightExperimentEndpoint:
    """Tests for POST /api/v1/diagnostics/weight-experiment."""

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_validates_weight_sum(self, mock_store, test_client) -> None:
        """Weights that do not sum to 1.0 should return 422."""
        payload = {
            "query": "test query",
            "max_docs": 5,
            "configurations": [
                {"fulltext": 0.5, "vector": 0.5, "knowledge_graph": 0.5}
            ],
        }

        response = test_client.post(
            "/api/v1/diagnostics/weight-experiment",
            json=payload,
        )

        assert response.status_code == 422
        body = response.json()
        # The app wraps HTTP errors in {"error": {"message": ...}} format
        error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "sum to 1.0" in error_msg.lower()

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_validates_multiple_configs(self, mock_store, test_client) -> None:
        """Each configuration should be individually validated."""
        payload = {
            "query": "test query",
            "max_docs": 5,
            "configurations": [
                {"fulltext": 0.4, "vector": 0.4, "knowledge_graph": 0.2},  # Valid
                {"fulltext": 0.3, "vector": 0.3, "knowledge_graph": 0.3},  # Invalid: 0.9
            ],
        }

        response = test_client.post(
            "/api/v1/diagnostics/weight-experiment",
            json=payload,
        )

        assert response.status_code == 422
        body = response.json()
        error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "Configuration 1" in error_msg

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_accepts_valid_weights(self, mock_store, test_client) -> None:
        """Valid weight configurations should not cause a weight-sum validation error.

        The full execution path imports hybrid_search_service which may error
        due to missing external services. We verify that the weight validation
        itself passes (no 422 with 'sum to 1.0' message). A downstream 500 is
        acceptable in this isolated test.
        """
        mock_store.store_trace = AsyncMock(return_value=True)
        payload = {
            "query": "test query",
            "max_docs": 5,
            "configurations": [
                {"fulltext": 0.4, "vector": 0.4, "knowledge_graph": 0.2},
            ],
        }

        response = test_client.post(
            "/api/v1/diagnostics/weight-experiment",
            json=payload,
        )

        # Should NOT be a 422 from our weight-sum validation.
        # It may be 422 from Pydantic or 500 from downstream services, but
        # never our custom "weights must sum to 1.0" error.
        if response.status_code == 422:
            body = response.json()
            error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
            assert "sum to 1.0" not in error_msg.lower(), (
                "Valid weights should not trigger sum-to-1.0 validation"
            )

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_empty_configurations_rejected(self, mock_store, test_client) -> None:
        """An empty configurations list should be rejected by Pydantic."""
        payload = {
            "query": "test query",
            "max_docs": 5,
            "configurations": [],
        }

        response = test_client.post(
            "/api/v1/diagnostics/weight-experiment",
            json=payload,
        )

        assert response.status_code == 422

    @patch("src.api.diagnostics.retrieval_diagnostics.diagnostics_store")
    def test_missing_query_rejected(self, mock_store, test_client) -> None:
        """A request without a query field should be rejected."""
        payload = {
            "max_docs": 5,
            "configurations": [
                {"fulltext": 0.4, "vector": 0.4, "knowledge_graph": 0.2},
            ],
        }

        response = test_client.post(
            "/api/v1/diagnostics/weight-experiment",
            json=payload,
        )

        assert response.status_code == 422


# ============================================================================
# Router Registration Tests
# ============================================================================


class TestDiagnosticsRouterRegistration:
    """Tests for diagnostics router configuration."""

    def test_router_prefix(self) -> None:
        """The diagnostics router should have /diagnostics prefix."""
        from src.api.diagnostics.retrieval_diagnostics import router

        assert router.prefix == "/diagnostics"

    def test_router_tags(self) -> None:
        """The diagnostics router should have diagnostics tag."""
        from src.api.diagnostics.retrieval_diagnostics import router

        assert "diagnostics" in router.tags

    def test_trace_route_exists(self) -> None:
        """GET /traces/{trace_id} route should be registered."""
        from src.api.diagnostics.retrieval_diagnostics import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        trace_routes = [r for r in routes if "{trace_id}" in r.path]
        assert len(trace_routes) >= 1

    def test_traces_list_route_exists(self) -> None:
        """GET /diagnostics/traces route should be registered."""
        from src.api.diagnostics.retrieval_diagnostics import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        list_routes = [r for r in routes if r.path.rstrip("/") in ("/traces", "/diagnostics/traces")]
        assert len(list_routes) >= 1

    def test_aggregate_route_exists(self) -> None:
        """GET /diagnostics/aggregate route should be registered."""
        from src.api.diagnostics.retrieval_diagnostics import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        aggregate_routes = [r for r in routes if r.path.rstrip("/") in ("/aggregate", "/diagnostics/aggregate")]
        assert len(aggregate_routes) >= 1

    def test_weight_experiment_route_exists(self) -> None:
        """POST /diagnostics/weight-experiment route should be registered."""
        from src.api.diagnostics.retrieval_diagnostics import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        experiment_routes = [r for r in routes if r.path.rstrip("/") in ("/weight-experiment", "/diagnostics/weight-experiment")]
        assert len(experiment_routes) >= 1
