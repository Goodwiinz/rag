"""Unit tests for BottleneckAnalyzer.

Tests cover:
- Healthy trace produces green health, no findings
- Failed source produces high severity finding and red health
- Zero-result source produces medium severity finding
- High truncation (>30%) produces high severity context finding
- Reranking fallback produces high severity finding
- Overall health aggregation (any red -> overall red, any yellow -> overall yellow)
- Empty trace (no sources) produces high severity finding
"""

import pytest

from src.services.diagnostics.bottleneck_analyzer import (
    TRUNCATION_HIGH_THRESHOLD,
    TRUNCATION_MEDIUM_THRESHOLD,
    BottleneckAnalyzer,
    BottleneckReport,
    Finding,
    PipelineStage,
    Severity,
)
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


def _make_healthy_trace() -> RetrievalTrace:
    """Factory for a fully healthy trace with no issues."""
    return RetrievalTrace(
        trace_id="healthy-001",
        query="machine learning basics",
        total_time_ms=150.0,
        sources=[
            SourceDiagnostics(
                source_type="fulltext",
                search_time_ms=40.0,
                result_count=10,
                total_available=50,
                success=True,
            ),
            SourceDiagnostics(
                source_type="vector",
                search_time_ms=60.0,
                result_count=8,
                total_available=30,
                success=True,
            ),
        ],
        fusion=FusionDiagnostics(
            input_count=18,
            output_count=12,
            multi_source_count=4,
            weights_used={"fulltext": 0.4, "vector": 0.4, "knowledge_graph": 0.2},
        ),
        rerank=RerankDiagnostics(enabled=True, rerank_time_ms=100.0, input_count=12, output_count=5),
        context=ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=5000,
            total_chars_after_truncation=5000,
            truncation_ratio=0.0,
        ),
        final_result_count=5,
    )


# ============================================================================
# Analyzer Instance
# ============================================================================


@pytest.fixture
def analyzer() -> BottleneckAnalyzer:
    """Create a fresh BottleneckAnalyzer for each test."""
    return BottleneckAnalyzer()


# ============================================================================
# Healthy Trace Tests
# ============================================================================


class TestHealthyTrace:
    """Tests for healthy traces producing clean reports."""

    def test_healthy_trace_green_overall(self, analyzer) -> None:
        """A healthy trace should produce overall green health."""
        trace = _make_healthy_trace()
        report = analyzer.analyze_trace(trace)

        assert report.overall_health == "green"

    def test_healthy_trace_no_findings(self, analyzer) -> None:
        """A healthy trace should produce no findings."""
        trace = _make_healthy_trace()
        report = analyzer.analyze_trace(trace)

        assert len(report.findings) == 0

    def test_healthy_trace_all_stages_green(self, analyzer) -> None:
        """A healthy trace should have green health for all stages."""
        trace = _make_healthy_trace()
        report = analyzer.analyze_trace(trace)

        for stage in [PipelineStage.SOURCE.value, PipelineStage.FUSION.value,
                      PipelineStage.RERANK.value, PipelineStage.CONTEXT.value]:
            assert report.stage_health[stage] == "green", (
                f"Stage '{stage}' should be green, got '{report.stage_health.get(stage)}'"
            )

    def test_report_has_correct_trace_id(self, analyzer) -> None:
        """The report should reference the correct trace_id."""
        trace = _make_healthy_trace()
        report = analyzer.analyze_trace(trace)

        assert report.trace_id == "healthy-001"


# ============================================================================
# Source Failure Tests
# ============================================================================


class TestSourceFailure:
    """Tests for source failures producing findings."""

    def test_failed_source_high_severity(self, analyzer) -> None:
        """A failed source should produce a HIGH severity finding."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="Connection refused",
        )

        report = analyzer.analyze_trace(trace)

        source_findings = [f for f in report.findings if f.stage == PipelineStage.SOURCE.value]
        assert len(source_findings) >= 1

        failure_finding = next(
            f for f in source_findings if f.severity == Severity.HIGH.value
        )
        assert "fulltext" in failure_finding.title.lower()
        assert "failed" in failure_finding.title.lower()
        assert "Connection refused" in failure_finding.detail

    def test_failed_source_red_health(self, analyzer) -> None:
        """A failed source should set source stage health to red."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="timeout",
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.SOURCE.value] == "red"

    def test_multiple_failed_sources(self, analyzer) -> None:
        """Multiple failed sources should each produce a finding."""
        trace = _make_healthy_trace()
        for i in range(len(trace.sources)):
            trace.sources[i] = SourceDiagnostics(
                source_type=trace.sources[i].source_type,
                search_time_ms=0.0,
                result_count=0,
                total_available=0,
                success=False,
                error=f"error-{i}",
            )

        report = analyzer.analyze_trace(trace)

        high_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.SOURCE.value and f.severity == Severity.HIGH.value
        ]
        assert len(high_findings) == 2


# ============================================================================
# Zero-Result Source Tests
# ============================================================================


class TestZeroResultSource:
    """Tests for sources returning zero results."""

    def test_zero_results_medium_severity(self, analyzer) -> None:
        """A zero-result source should produce a MEDIUM severity finding."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=50.0,
            result_count=0,
            total_available=0,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        zero_findings = [
            f for f in report.findings
            if f.severity == Severity.MEDIUM.value
            and "zero" in f.title.lower()
        ]
        assert len(zero_findings) == 1
        assert "fulltext" in zero_findings[0].title.lower()

    def test_zero_results_yellow_health(self, analyzer) -> None:
        """A zero-result source should set source stage health to yellow."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=50.0,
            result_count=0,
            total_available=0,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.SOURCE.value] == "yellow"

    def test_zero_results_not_overridden_by_failure(self, analyzer) -> None:
        """If one source fails and another has zero results, red should win."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="error",
        )
        trace.sources[1] = SourceDiagnostics(
            source_type="vector",
            search_time_ms=50.0,
            result_count=0,
            total_available=0,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.SOURCE.value] == "red"


# ============================================================================
# Slow Source Tests
# ============================================================================


class TestSlowSource:
    """Tests for slow source detection."""

    def test_slow_source_low_severity(self, analyzer) -> None:
        """A slow source (>2000ms) should produce a LOW severity finding."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=2500.0,
            result_count=10,
            total_available=50,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        slow_findings = [
            f for f in report.findings
            if f.severity == Severity.LOW.value and "slow" in f.title.lower()
        ]
        assert len(slow_findings) == 1

    def test_slow_source_yellow_health(self, analyzer) -> None:
        """A slow source should set source stage health to yellow."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=3000.0,
            result_count=10,
            total_available=50,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.SOURCE.value] == "yellow"


# ============================================================================
# Context Truncation Tests
# ============================================================================


class TestContextTruncation:
    """Tests for context truncation findings."""

    def test_high_truncation_high_severity(self, analyzer) -> None:
        """Truncation ratio >30% should produce a HIGH severity finding."""
        trace = _make_healthy_trace()
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=10000,
            total_chars_after_truncation=6000,
            truncation_ratio=0.40,
            truncated_docs=[{"doc_id": "d1", "before": 3000, "after": 1500}],
        )

        report = analyzer.analyze_trace(trace)

        ctx_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.CONTEXT.value and f.severity == Severity.HIGH.value
        ]
        assert len(ctx_findings) >= 1
        assert "truncation" in ctx_findings[0].title.lower()

    def test_high_truncation_red_context_health(self, analyzer) -> None:
        """High truncation should set context stage health to red."""
        trace = _make_healthy_trace()
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=10000,
            total_chars_after_truncation=5000,
            truncation_ratio=0.50,
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.CONTEXT.value] == "red"

    def test_moderate_truncation_medium_severity(self, analyzer) -> None:
        """Truncation ratio 15-30% should produce a MEDIUM severity finding."""
        trace = _make_healthy_trace()
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=10000,
            total_chars_after_truncation=8000,
            truncation_ratio=0.20,
        )

        report = analyzer.analyze_trace(trace)

        ctx_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.CONTEXT.value and f.severity == Severity.MEDIUM.value
        ]
        assert len(ctx_findings) == 1
        assert report.stage_health[PipelineStage.CONTEXT.value] == "yellow"

    def test_no_truncation_no_finding(self, analyzer) -> None:
        """Zero truncation should produce no context findings."""
        trace = _make_healthy_trace()
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=5000,
            total_chars_after_truncation=5000,
            truncation_ratio=0.0,
        )

        report = analyzer.analyze_trace(trace)

        ctx_findings = [
            f for f in report.findings if f.stage == PipelineStage.CONTEXT.value
        ]
        assert len(ctx_findings) == 0
        assert report.stage_health[PipelineStage.CONTEXT.value] == "green"

    def test_docs_with_no_content_high_severity(self, analyzer) -> None:
        """Docs retrieved but none with content should produce HIGH severity."""
        trace = _make_healthy_trace()
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=0,
            total_chars_before_truncation=0,
            total_chars_after_truncation=0,
            truncation_ratio=0.0,
        )

        report = analyzer.analyze_trace(trace)

        ctx_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.CONTEXT.value and f.severity == Severity.HIGH.value
        ]
        assert len(ctx_findings) >= 1
        assert "no content" in ctx_findings[0].title.lower()


# ============================================================================
# Reranking Fallback Tests
# ============================================================================


class TestRerankingFallback:
    """Tests for reranking fallback detection."""

    def test_reranking_fallback_high_severity(self, analyzer) -> None:
        """Reranking fallback should produce a HIGH severity finding."""
        trace = _make_healthy_trace()
        trace.rerank = RerankDiagnostics(
            enabled=True,
            rerank_time_ms=200.0,
            input_count=12,
            output_count=12,
            fallback_used=True,
            error="Cohere API key expired",
        )

        report = analyzer.analyze_trace(trace)

        rerank_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.RERANK.value and f.severity == Severity.HIGH.value
        ]
        assert len(rerank_findings) == 1
        assert "fallback" in rerank_findings[0].title.lower()
        assert "Cohere API key expired" in rerank_findings[0].detail

    def test_reranking_fallback_red_health(self, analyzer) -> None:
        """Reranking fallback should set rerank stage health to red."""
        trace = _make_healthy_trace()
        trace.rerank = RerankDiagnostics(
            enabled=True,
            fallback_used=True,
            error="API error",
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.RERANK.value] == "red"

    def test_reranking_disabled_green_health(self, analyzer) -> None:
        """Disabled reranking should produce green health with no findings."""
        trace = _make_healthy_trace()
        trace.rerank = RerankDiagnostics(enabled=False)

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.RERANK.value] == "green"
        rerank_findings = [
            f for f in report.findings if f.stage == PipelineStage.RERANK.value
        ]
        assert len(rerank_findings) == 0

    def test_slow_reranking_yellow_health(self, analyzer) -> None:
        """Slow reranking (>2000ms) should produce LOW finding and yellow health."""
        trace = _make_healthy_trace()
        trace.rerank = RerankDiagnostics(
            enabled=True,
            rerank_time_ms=3000.0,
            input_count=20,
            output_count=10,
        )

        report = analyzer.analyze_trace(trace)

        slow_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.RERANK.value and "slow" in f.title.lower()
        ]
        assert len(slow_findings) == 1
        assert report.stage_health[PipelineStage.RERANK.value] == "yellow"


# ============================================================================
# Fusion Tests
# ============================================================================


class TestFusionAnalysis:
    """Tests for fusion stage analysis."""

    def test_low_fusion_output_medium_severity(self, analyzer) -> None:
        """Low fusion output (<3 docs) should produce MEDIUM finding."""
        trace = _make_healthy_trace()
        trace.fusion = FusionDiagnostics(
            input_count=10,
            output_count=2,
            multi_source_count=0,
        )

        report = analyzer.analyze_trace(trace)

        fusion_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.FUSION.value and f.severity == Severity.MEDIUM.value
        ]
        assert len(fusion_findings) >= 1
        assert report.stage_health[PipelineStage.FUSION.value] == "yellow"

    def test_no_cross_source_overlap_low_severity(self, analyzer) -> None:
        """No cross-source overlap should produce LOW finding."""
        trace = _make_healthy_trace()
        trace.fusion = FusionDiagnostics(
            input_count=20,
            output_count=15,
            multi_source_count=0,
        )

        report = analyzer.analyze_trace(trace)

        overlap_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.FUSION.value
            and f.severity == Severity.LOW.value
            and "overlap" in f.title.lower()
        ]
        assert len(overlap_findings) == 1

    def test_no_fusion_green_health(self, analyzer) -> None:
        """Absent fusion stage should produce green health."""
        trace = _make_healthy_trace()
        trace.fusion = None

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.FUSION.value] == "green"


# ============================================================================
# Overall Health Aggregation Tests
# ============================================================================


class TestOverallHealth:
    """Tests for overall health aggregation logic."""

    def test_all_green_overall_green(self, analyzer) -> None:
        """When all stages are green, overall should be green."""
        trace = _make_healthy_trace()
        report = analyzer.analyze_trace(trace)

        assert report.overall_health == "green"

    def test_any_red_overall_red(self, analyzer) -> None:
        """Any red stage should set overall health to red."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="failure",
        )

        report = analyzer.analyze_trace(trace)

        assert report.overall_health == "red"

    def test_any_yellow_overall_yellow(self, analyzer) -> None:
        """Any yellow stage (with no reds) should set overall to yellow."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=50.0,
            result_count=0,
            total_available=0,
            success=True,
        )

        report = analyzer.analyze_trace(trace)

        assert report.overall_health == "yellow"

    def test_red_overrides_yellow(self, analyzer) -> None:
        """Red in one stage should produce overall red even if another is yellow."""
        trace = _make_healthy_trace()
        # Source: red (failure)
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="error",
        )
        # Context: yellow (moderate truncation)
        trace.context = ContextDiagnostics(
            docs_retrieved=5,
            docs_with_content=5,
            total_chars_before_truncation=10000,
            total_chars_after_truncation=8000,
            truncation_ratio=0.20,
        )

        report = analyzer.analyze_trace(trace)

        assert report.overall_health == "red"


# ============================================================================
# Empty Trace Tests
# ============================================================================


class TestEmptyTrace:
    """Tests for traces with no sources."""

    def test_no_sources_high_severity(self, analyzer) -> None:
        """A trace with no sources should produce a HIGH severity finding."""
        trace = RetrievalTrace(
            trace_id="empty-001",
            query="test query",
            sources=[],
        )

        report = analyzer.analyze_trace(trace)

        source_findings = [
            f for f in report.findings
            if f.stage == PipelineStage.SOURCE.value and f.severity == Severity.HIGH.value
        ]
        assert len(source_findings) == 1
        assert "no search sources" in source_findings[0].title.lower()

    def test_no_sources_red_health(self, analyzer) -> None:
        """A trace with no sources should set source stage health to red."""
        trace = RetrievalTrace(
            trace_id="empty-002",
            sources=[],
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.SOURCE.value] == "red"
        assert report.overall_health == "red"

    def test_no_optional_stages_green(self, analyzer) -> None:
        """Missing optional stages (fusion, rerank, context) should be green."""
        trace = RetrievalTrace(
            trace_id="minimal",
            sources=[
                SourceDiagnostics(
                    source_type="fulltext",
                    search_time_ms=50.0,
                    result_count=5,
                    total_available=20,
                    success=True,
                ),
            ],
        )

        report = analyzer.analyze_trace(trace)

        assert report.stage_health[PipelineStage.FUSION.value] == "green"
        assert report.stage_health[PipelineStage.RERANK.value] == "green"
        assert report.stage_health[PipelineStage.CONTEXT.value] == "green"


# ============================================================================
# Finding / Report Serialization Tests
# ============================================================================


class TestFindingSerialization:
    """Tests for Finding and BottleneckReport serialization."""

    def test_finding_to_dict(self) -> None:
        """Finding.to_dict() should produce a correct dictionary."""
        finding = Finding(
            stage="source",
            severity="high",
            title="Test finding",
            detail="Some detail",
            recommendation="Do something",
        )
        d = finding.to_dict()

        assert d["stage"] == "source"
        assert d["severity"] == "high"
        assert d["title"] == "Test finding"
        assert d["detail"] == "Some detail"
        assert d["recommendation"] == "Do something"

    def test_finding_from_dict(self) -> None:
        """Finding.from_dict() should reconstruct from a dictionary."""
        d = {
            "stage": "context",
            "severity": "medium",
            "title": "Moderate truncation",
            "detail": "20% lost",
            "recommendation": "Monitor quality",
        }
        finding = Finding.from_dict(d)

        assert finding.stage == "context"
        assert finding.severity == "medium"
        assert finding.title == "Moderate truncation"

    def test_report_to_dict(self, analyzer) -> None:
        """BottleneckReport.to_dict() should serialize findings and stage_health."""
        trace = _make_healthy_trace()
        trace.sources[0] = SourceDiagnostics(
            source_type="fulltext",
            search_time_ms=0.0,
            result_count=0,
            total_available=0,
            success=False,
            error="error",
        )

        report = analyzer.analyze_trace(trace)
        d = report.to_dict()

        assert d["trace_id"] == "healthy-001"
        assert isinstance(d["findings"], list)
        assert len(d["findings"]) >= 1
        assert isinstance(d["stage_health"], dict)
        assert d["overall_health"] in ("green", "yellow", "red")
