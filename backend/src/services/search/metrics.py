"""
Search Metrics Service

Tracks search performance, analytics, and quality metrics
for monitoring and optimization.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base import SearchQuery, SearchResult, SearchSource

logger = logging.getLogger(__name__)


@dataclass
class SearchMetricEvent:
    """A single search metric event."""

    query_text: str
    results_count: int
    execution_time_ms: float
    sources_used: List[SearchSource]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    cache_hit: bool = False
    reranked: bool = False
    error: Optional[str] = None

    # Quality metrics
    avg_score: float = 0.0
    top_score: float = 0.0
    source_distribution: Dict[str, int] = field(default_factory=dict)


class SearchMetrics:
    """
    Service for tracking and reporting search metrics.

    Collects:
    - Query performance (latency, result counts)
    - Source utilization
    - Cache effectiveness
    - Error rates
    - Quality indicators
    """

    def __init__(self, retention_hours: int = 24, max_events: int = 10000):
        """
        Initialize the metrics service.

        Args:
            retention_hours: Hours to retain metrics
            max_events: Maximum events to store in memory
        """
        self.retention_hours = retention_hours
        self.max_events = max_events

        self._events: List[SearchMetricEvent] = []
        self._aggregates = self._init_aggregates()
        self._start_time = datetime.now(timezone.utc)

    def _init_aggregates(self) -> Dict[str, Any]:
        """Initialize aggregate metrics."""
        return {
            "total_searches": 0,
            "total_results": 0,
            "total_time_ms": 0.0,
            "cache_hits": 0,
            "errors": 0,
            "source_usage": defaultdict(int),
            "latency_buckets": {
                "<100ms": 0,
                "100-500ms": 0,
                "500-1000ms": 0,
                "1000-2000ms": 0,
                ">2000ms": 0,
            },
        }

    def record_search(
        self,
        query: SearchQuery,
        results: List[SearchResult],
        execution_time_ms: float,
        sources_used: List[SearchSource],
        cache_hit: bool = False,
        reranked: bool = False,
        error: Optional[str] = None,
    ):
        """
        Record a search event.

        Args:
            query: The search query
            results: Search results
            execution_time_ms: Execution time in milliseconds
            sources_used: Sources that contributed results
            cache_hit: Whether result was from cache
            reranked: Whether results were reranked
            error: Error message if search failed
        """
        # Calculate quality metrics
        avg_score = 0.0
        top_score = 0.0
        source_distribution: Dict[str, int] = defaultdict(int)

        if results:
            scores = [r.score for r in results]
            avg_score = sum(scores) / len(scores)
            top_score = max(scores)

            for r in results:
                sources = r.metadata.get("fusion_sources", [r.source.value])
                for s in sources if isinstance(sources, list) else [sources]:
                    source_distribution[s] += 1

        # Create event
        event = SearchMetricEvent(
            query_text=query.text,
            results_count=len(results),
            execution_time_ms=execution_time_ms,
            sources_used=sources_used,
            user_id=query.user_id,
            cache_hit=cache_hit,
            reranked=reranked,
            error=error,
            avg_score=avg_score,
            top_score=top_score,
            source_distribution=dict(source_distribution),
        )

        # Store event
        self._events.append(event)

        # Update aggregates
        self._update_aggregates(event)

        # Cleanup old events if needed
        self._cleanup_old_events()

        # Log high latency searches
        if execution_time_ms > 2000:
            logger.warning(
                f"Slow search: {execution_time_ms:.0f}ms for query '{query.text[:50]}'"
            )

    def _update_aggregates(self, event: SearchMetricEvent):
        """Update aggregate metrics with new event."""
        self._aggregates["total_searches"] += 1
        self._aggregates["total_results"] += event.results_count
        self._aggregates["total_time_ms"] += event.execution_time_ms

        if event.cache_hit:
            self._aggregates["cache_hits"] += 1

        if event.error:
            self._aggregates["errors"] += 1

        for source in event.sources_used:
            self._aggregates["source_usage"][source.value] += 1

        # Update latency buckets
        latency = event.execution_time_ms
        if latency < 100:
            self._aggregates["latency_buckets"]["<100ms"] += 1
        elif latency < 500:
            self._aggregates["latency_buckets"]["100-500ms"] += 1
        elif latency < 1000:
            self._aggregates["latency_buckets"]["500-1000ms"] += 1
        elif latency < 2000:
            self._aggregates["latency_buckets"]["1000-2000ms"] += 1
        else:
            self._aggregates["latency_buckets"][">2000ms"] += 1

    def _cleanup_old_events(self):
        """Remove events older than retention period."""
        if len(self._events) > self.max_events:
            # Keep only the most recent events
            self._events = self._events[-self.max_events :]

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        self._events = [e for e in self._events if e.timestamp > cutoff]

    def record_source_failure(self, source: SearchSource, error: Exception):
        """Record a source failure."""
        logger.error(f"Search source {source.value} failed: {error}")
        self._aggregates["errors"] += 1

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of search metrics.

        Returns:
            Dictionary with metric summary
        """
        total = self._aggregates["total_searches"]

        if total == 0:
            return {
                "total_searches": 0,
                "message": "No searches recorded yet",
            }

        avg_latency = self._aggregates["total_time_ms"] / total
        avg_results = self._aggregates["total_results"] / total
        cache_rate = self._aggregates["cache_hits"] / total * 100
        error_rate = self._aggregates["errors"] / total * 100

        return {
            "total_searches": total,
            "avg_latency_ms": round(avg_latency, 2),
            "avg_results_per_search": round(avg_results, 2),
            "cache_hit_rate_pct": round(cache_rate, 2),
            "error_rate_pct": round(error_rate, 2),
            "source_usage": dict(self._aggregates["source_usage"]),
            "latency_distribution": self._aggregates["latency_buckets"],
            "uptime_hours": round(
                (datetime.now(timezone.utc) - self._start_time).total_seconds() / 3600,
                2,
            ),
        }

    def get_recent_events(
        self, limit: int = 100, include_errors_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get recent search events.

        Args:
            limit: Maximum events to return
            include_errors_only: Only return events with errors

        Returns:
            List of event dictionaries
        """
        events = self._events

        if include_errors_only:
            events = [e for e in events if e.error]

        recent = events[-limit:]

        return [
            {
                "query": e.query_text[:100],
                "results_count": e.results_count,
                "execution_time_ms": round(e.execution_time_ms, 2),
                "sources": [s.value for s in e.sources_used],
                "timestamp": e.timestamp.isoformat(),
                "cache_hit": e.cache_hit,
                "error": e.error,
            }
            for e in reversed(recent)
        ]

    def get_quality_metrics(self) -> Dict[str, Any]:
        """
        Get quality metrics from recent searches.

        Returns:
            Dictionary with quality metrics
        """
        if not self._events:
            return {"message": "No searches recorded yet"}

        recent_events = self._events[-1000:]  # Last 1000 events

        scores = [e.avg_score for e in recent_events if e.avg_score > 0]
        top_scores = [e.top_score for e in recent_events if e.top_score > 0]

        if not scores:
            return {"message": "No scored results available"}

        return {
            "avg_result_score": round(sum(scores) / len(scores), 4),
            "avg_top_score": round(sum(top_scores) / len(top_scores), 4),
            "zero_result_rate_pct": round(
                len([e for e in recent_events if e.results_count == 0])
                / len(recent_events)
                * 100,
                2,
            ),
            "sample_size": len(recent_events),
        }

    def reset(self):
        """Reset all metrics."""
        self._events = []
        self._aggregates = self._init_aggregates()
        self._start_time = datetime.now(timezone.utc)
        logger.info("Search metrics reset")
