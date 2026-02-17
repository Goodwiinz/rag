"""
Bottleneck analyzer for retrieval diagnostic traces.

Examines a RetrievalTrace and identifies quality issues across
the pipeline: source failures, low result counts, reranking problems,
high truncation loss, and low source diversity.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from .retrieval_diagnostics import RetrievalTrace

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PipelineStage(str, Enum):
    SOURCE = "source"
    FUSION = "fusion"
    RERANK = "rerank"
    CONTEXT = "context"


@dataclass
class Finding:
    """A single bottleneck finding."""

    stage: str
    severity: str
    title: str
    detail: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        return cls(**data)


@dataclass
class BottleneckReport:
    """Full bottleneck analysis report for a trace."""

    trace_id: str
    findings: List[Finding] = field(default_factory=list)
    stage_health: Dict[str, str] = field(default_factory=dict)  # stage -> green/yellow/red
    overall_health: str = "green"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "findings": [f.to_dict() for f in self.findings],
            "stage_health": self.stage_health,
            "overall_health": self.overall_health,
        }


# Thresholds (aligned with success_criteria.py)
TRUNCATION_HIGH_THRESHOLD = 0.30  # >30% content lost
TRUNCATION_MEDIUM_THRESHOLD = 0.15
MIN_EXPECTED_RESULTS = 3
SLOW_SOURCE_MS = 2000  # P95 latency target from success_criteria


class BottleneckAnalyzer:
    """Analyzes a RetrievalTrace to identify pipeline bottlenecks."""

    def analyze_trace(self, trace: RetrievalTrace) -> BottleneckReport:
        report = BottleneckReport(trace_id=trace.trace_id)

        self._check_sources(trace, report)
        self._check_fusion(trace, report)
        self._check_rerank(trace, report)
        self._check_context(trace, report)
        self._compute_overall_health(report)

        return report

    def _check_sources(self, trace: RetrievalTrace, report: BottleneckReport) -> None:
        stage = PipelineStage.SOURCE.value
        health = "green"

        for src in trace.sources:
            if not src.success:
                report.findings.append(
                    Finding(
                        stage=stage,
                        severity=Severity.HIGH.value,
                        title=f"{src.source_type} search failed",
                        detail=f"Error: {src.error or 'unknown'}",
                        recommendation=f"Check {src.source_type} service connectivity and logs.",
                    )
                )
                health = "red"
            elif src.result_count == 0:
                report.findings.append(
                    Finding(
                        stage=stage,
                        severity=Severity.MEDIUM.value,
                        title=f"{src.source_type} returned zero results",
                        detail=f"Searched in {src.search_time_ms:.0f}ms but found nothing.",
                        recommendation=f"Check if documents are indexed in {src.source_type} store. Consider broadening the query.",
                    )
                )
                if health != "red":
                    health = "yellow"
            elif src.search_time_ms > SLOW_SOURCE_MS:
                report.findings.append(
                    Finding(
                        stage=stage,
                        severity=Severity.LOW.value,
                        title=f"{src.source_type} is slow ({src.search_time_ms:.0f}ms)",
                        detail=f"Exceeds {SLOW_SOURCE_MS}ms threshold.",
                        recommendation=f"Investigate {src.source_type} performance. Consider adding indices or caching.",
                    )
                )
                if health == "green":
                    health = "yellow"

        if not trace.sources:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.HIGH.value,
                    title="No search sources executed",
                    detail="Pipeline produced no source results.",
                    recommendation="Check search routing configuration.",
                )
            )
            health = "red"

        report.stage_health[stage] = health

    def _check_fusion(self, trace: RetrievalTrace, report: BottleneckReport) -> None:
        stage = PipelineStage.FUSION.value

        if not trace.fusion:
            report.stage_health[stage] = "green"
            return

        health = "green"
        fusion = trace.fusion

        if fusion.output_count < MIN_EXPECTED_RESULTS:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.MEDIUM.value,
                    title=f"Low fusion output ({fusion.output_count} docs)",
                    detail=f"Only {fusion.output_count} unique docs from {fusion.input_count} raw results.",
                    recommendation="Sources may be returning overlapping or insufficient results.",
                )
            )
            health = "yellow"

        if fusion.multi_source_count == 0 and fusion.output_count > 0:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.LOW.value,
                    title="No cross-source overlap",
                    detail="No documents appeared in multiple sources. Diversity boost had no effect.",
                    recommendation="This may indicate the query is too narrow or sources index different content.",
                )
            )

        report.stage_health[stage] = health

    def _check_rerank(self, trace: RetrievalTrace, report: BottleneckReport) -> None:
        stage = PipelineStage.RERANK.value

        if not trace.rerank:
            report.stage_health[stage] = "green"
            return

        health = "green"
        rerank = trace.rerank

        if not rerank.enabled:
            report.stage_health[stage] = "green"
            return

        if rerank.fallback_used:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.HIGH.value,
                    title="Reranking fallback activated",
                    detail=f"Cohere reranking failed: {rerank.error or 'unknown error'}. Original order used.",
                    recommendation="Check Cohere API key and connectivity. Results may have lower precision.",
                )
            )
            health = "red"
        elif rerank.rerank_time_ms > SLOW_SOURCE_MS:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.LOW.value,
                    title=f"Reranking is slow ({rerank.rerank_time_ms:.0f}ms)",
                    detail=f"Reranking {rerank.input_count} docs took {rerank.rerank_time_ms:.0f}ms.",
                    recommendation="Consider reducing the number of documents sent to reranking.",
                )
            )
            if health == "green":
                health = "yellow"

        report.stage_health[stage] = health

    def _check_context(self, trace: RetrievalTrace, report: BottleneckReport) -> None:
        stage = PipelineStage.CONTEXT.value

        if not trace.context:
            report.stage_health[stage] = "green"
            return

        health = "green"
        ctx = trace.context

        if ctx.truncation_ratio > TRUNCATION_HIGH_THRESHOLD:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.HIGH.value,
                    title=f"High context truncation ({ctx.truncation_ratio:.0%})",
                    detail=(
                        f"{ctx.total_chars_before_truncation} chars truncated to "
                        f"{ctx.total_chars_after_truncation} chars ({len(ctx.truncated_docs)} docs affected)."
                    ),
                    recommendation=(
                        "Consider increasing the context limit, using summarization, "
                        "or retrieving fewer but more relevant documents."
                    ),
                )
            )
            health = "red"
        elif ctx.truncation_ratio > TRUNCATION_MEDIUM_THRESHOLD:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.MEDIUM.value,
                    title=f"Moderate context truncation ({ctx.truncation_ratio:.0%})",
                    detail=(
                        f"{ctx.total_chars_before_truncation} chars truncated to "
                        f"{ctx.total_chars_after_truncation} chars."
                    ),
                    recommendation="Some context is being lost. Monitor answer quality for impact.",
                )
            )
            health = "yellow"

        if ctx.docs_with_content == 0 and ctx.docs_retrieved > 0:
            report.findings.append(
                Finding(
                    stage=stage,
                    severity=Severity.HIGH.value,
                    title="Retrieved docs have no content",
                    detail=f"{ctx.docs_retrieved} docs retrieved but none had extractable content.",
                    recommendation="Check document processing pipeline — content may not be stored correctly.",
                )
            )
            health = "red"

        report.stage_health[stage] = health

    def _compute_overall_health(self, report: BottleneckReport) -> None:
        if any(h == "red" for h in report.stage_health.values()):
            report.overall_health = "red"
        elif any(h == "yellow" for h in report.stage_health.values()):
            report.overall_health = "yellow"
        else:
            report.overall_health = "green"
