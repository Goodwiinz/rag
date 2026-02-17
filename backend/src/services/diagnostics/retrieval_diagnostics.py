"""
Data model for retrieval diagnostics traces.

Each dataclass captures timing, counts, scores, and issues for a specific
pipeline stage. A RetrievalTrace aggregates all stages for a single query.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SourceDiagnostics:
    """Diagnostics for a single search source (fulltext, vector, or knowledge_graph)."""

    source_type: str
    search_time_ms: float
    result_count: int
    total_available: int
    success: bool
    error: Optional[str] = None
    top_scores: List[float] = field(default_factory=list)
    avg_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "search_time_ms": self.search_time_ms,
            "result_count": self.result_count,
            "total_available": self.total_available,
            "success": self.success,
            "error": self.error,
            "top_scores": self.top_scores,
            "avg_score": self.avg_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceDiagnostics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class FusionDiagnostics:
    """Diagnostics for the score fusion stage."""

    input_count: int  # Total docs before fusion
    output_count: int  # Unique docs after fusion
    multi_source_count: int  # Docs appearing in multiple sources
    weights_used: Dict[str, float] = field(default_factory=dict)
    score_distribution: Dict[str, float] = field(default_factory=dict)  # min, max, mean, median
    fusion_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "multi_source_count": self.multi_source_count,
            "weights_used": self.weights_used,
            "score_distribution": self.score_distribution,
            "fusion_time_ms": self.fusion_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FusionDiagnostics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RerankDiagnostics:
    """Diagnostics for the Cohere reranking stage."""

    enabled: bool
    rerank_time_ms: float = 0.0
    input_count: int = 0
    output_count: int = 0
    score_deltas: List[Dict[str, Any]] = field(default_factory=list)  # [{doc_id, before, after, delta}]
    fallback_used: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "rerank_time_ms": self.rerank_time_ms,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "score_deltas": self.score_deltas,
            "fallback_used": self.fallback_used,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RerankDiagnostics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ContextDiagnostics:
    """Diagnostics for the context assembly and truncation stage."""

    docs_retrieved: int
    docs_with_content: int
    total_chars_before_truncation: int
    total_chars_after_truncation: int
    truncated_docs: List[Dict[str, Any]] = field(default_factory=list)  # [{doc_id, before, after}]
    truncation_ratio: float = 0.0  # chars_lost / chars_before
    char_limit: int = 3000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "docs_retrieved": self.docs_retrieved,
            "docs_with_content": self.docs_with_content,
            "total_chars_before_truncation": self.total_chars_before_truncation,
            "total_chars_after_truncation": self.total_chars_after_truncation,
            "truncated_docs": self.truncated_docs,
            "truncation_ratio": self.truncation_ratio,
            "char_limit": self.char_limit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextDiagnostics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RetrievalTrace:
    """Full diagnostic trace for a single retrieval query."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_time_ms: float = 0.0

    # Pipeline stages
    sources: List[SourceDiagnostics] = field(default_factory=list)
    fusion: Optional[FusionDiagnostics] = None
    rerank: Optional[RerankDiagnostics] = None
    context: Optional[ContextDiagnostics] = None

    # Final results
    final_result_count: int = 0
    search_type: str = "hybrid"

    # Linked evaluation (populated async by background eval)
    evaluation_id: Optional[str] = None
    evaluation_scores: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "timestamp": self.timestamp,
            "total_time_ms": self.total_time_ms,
            "sources": [s.to_dict() for s in self.sources],
            "fusion": self.fusion.to_dict() if self.fusion else None,
            "rerank": self.rerank.to_dict() if self.rerank else None,
            "context": self.context.to_dict() if self.context else None,
            "final_result_count": self.final_result_count,
            "search_type": self.search_type,
            "evaluation_id": self.evaluation_id,
            "evaluation_scores": self.evaluation_scores,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalTrace":
        sources = [SourceDiagnostics.from_dict(s) for s in data.get("sources", [])]
        fusion = FusionDiagnostics.from_dict(data["fusion"]) if data.get("fusion") else None
        rerank = RerankDiagnostics.from_dict(data["rerank"]) if data.get("rerank") else None
        context = ContextDiagnostics.from_dict(data["context"]) if data.get("context") else None

        return cls(
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            query=data.get("query", ""),
            timestamp=data.get("timestamp", ""),
            total_time_ms=data.get("total_time_ms", 0.0),
            sources=sources,
            fusion=fusion,
            rerank=rerank,
            context=context,
            final_result_count=data.get("final_result_count", 0),
            search_type=data.get("search_type", "hybrid"),
            evaluation_id=data.get("evaluation_id"),
            evaluation_scores=data.get("evaluation_scores"),
        )
