"""
Redis-backed store for retrieval diagnostic traces.

Stores traces with a 24-hour TTL and provides retrieval by ID,
recent trace listing, and aggregate statistics.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .retrieval_diagnostics import RetrievalTrace

logger = logging.getLogger(__name__)

TRACE_KEY_PREFIX = "diag:trace:"
TRACE_INDEX_KEY = "diag:traces:index"
TRACE_TTL_SECONDS = 86400  # 24 hours


class DiagnosticsStore:
    """Stores and retrieves diagnostic traces in Redis."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def redis(self):
        """Lazy access to Redis client, falling back to global if not set."""
        if self._redis is not None:
            return self._redis
        try:
            from src.main import redis_client

            return redis_client
        except ImportError:
            return None

    async def store_trace(self, trace: RetrievalTrace) -> bool:
        """Store a diagnostic trace. Returns True on success."""
        client = self.redis
        if client is None:
            logger.warning("No Redis client available, trace not stored")
            return False

        try:
            key = f"{TRACE_KEY_PREFIX}{trace.trace_id}"
            data = json.dumps(trace.to_dict())

            # Store trace data with TTL
            if hasattr(client, "set") and hasattr(client.set, "__await__"):
                # Async redis
                await client.set(key, data, ex=TRACE_TTL_SECONDS)
                await client.zadd(
                    TRACE_INDEX_KEY,
                    {trace.trace_id: datetime.now(timezone.utc).timestamp()},
                )
                # Trim index to last 1000 entries
                await client.zremrangebyrank(TRACE_INDEX_KEY, 0, -1001)
            else:
                # Sync redis
                client.set(key, data, ex=TRACE_TTL_SECONDS)
                client.zadd(
                    TRACE_INDEX_KEY,
                    {trace.trace_id: datetime.now(timezone.utc).timestamp()},
                )
                client.zremrangebyrank(TRACE_INDEX_KEY, 0, -1001)

            return True
        except Exception as e:
            logger.error(f"Failed to store trace {trace.trace_id}: {e}")
            return False

    async def get_trace(self, trace_id: str) -> Optional[RetrievalTrace]:
        """Retrieve a single trace by ID."""
        client = self.redis
        if client is None:
            return None

        try:
            key = f"{TRACE_KEY_PREFIX}{trace_id}"
            if hasattr(client, "get") and hasattr(client.get, "__await__"):
                data = await client.get(key)
            else:
                data = client.get(key)

            if data is None:
                return None

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return RetrievalTrace.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Failed to get trace {trace_id}: {e}")
            return None

    async def get_recent_traces(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recent trace summaries (trace_id, query, timestamp, total_time_ms)."""
        client = self.redis
        if client is None:
            return []

        try:
            # Get trace IDs from sorted set (most recent first)
            if hasattr(client, "zrevrange") and hasattr(client.zrevrange, "__await__"):
                trace_ids = await client.zrevrange(
                    TRACE_INDEX_KEY, offset, offset + limit - 1
                )
            else:
                trace_ids = client.zrevrange(
                    TRACE_INDEX_KEY, offset, offset + limit - 1
                )

            summaries = []
            for tid in trace_ids:
                if isinstance(tid, bytes):
                    tid = tid.decode("utf-8")

                trace = await self.get_trace(tid)
                if trace:
                    summaries.append(
                        {
                            "trace_id": trace.trace_id,
                            "query": trace.query[:100],
                            "timestamp": trace.timestamp,
                            "total_time_ms": trace.total_time_ms,
                            "final_result_count": trace.final_result_count,
                            "search_type": trace.search_type,
                            "source_count": len(trace.sources),
                            "has_evaluation": trace.evaluation_id is not None,
                        }
                    )

            return summaries
        except Exception as e:
            logger.error(f"Failed to get recent traces: {e}")
            return []

    async def get_aggregate_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Compute aggregate statistics over recent traces."""
        client = self.redis
        if client is None:
            return {"error": "Redis unavailable"}

        try:
            cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)

            if hasattr(client, "zrangebyscore") and hasattr(
                client.zrangebyscore, "__await__"
            ):
                trace_ids = await client.zrangebyscore(
                    TRACE_INDEX_KEY, cutoff, "+inf"
                )
            else:
                trace_ids = client.zrangebyscore(
                    TRACE_INDEX_KEY, cutoff, "+inf"
                )

            if not trace_ids:
                return {
                    "period_hours": hours,
                    "total_traces": 0,
                    "avg_time_ms": 0,
                    "source_stats": {},
                    "truncation_stats": {},
                }

            total_time = 0.0
            source_times: Dict[str, List[float]] = {}
            source_failures = 0
            truncation_ratios: List[float] = []
            result_counts: List[int] = []

            for tid in trace_ids:
                if isinstance(tid, bytes):
                    tid = tid.decode("utf-8")

                trace = await self.get_trace(tid)
                if not trace:
                    continue

                total_time += trace.total_time_ms
                result_counts.append(trace.final_result_count)

                for src in trace.sources:
                    source_times.setdefault(src.source_type, []).append(
                        src.search_time_ms
                    )
                    if not src.success:
                        source_failures += 1

                if trace.context:
                    truncation_ratios.append(trace.context.truncation_ratio)

            count = len(trace_ids)
            return {
                "period_hours": hours,
                "total_traces": count,
                "avg_time_ms": round(total_time / count, 2) if count else 0,
                "avg_result_count": round(sum(result_counts) / count, 1)
                if count
                else 0,
                "source_stats": {
                    src_type: {
                        "avg_time_ms": round(sum(times) / len(times), 2),
                        "max_time_ms": round(max(times), 2),
                        "query_count": len(times),
                    }
                    for src_type, times in source_times.items()
                },
                "source_failure_count": source_failures,
                "truncation_stats": {
                    "avg_ratio": round(
                        sum(truncation_ratios) / len(truncation_ratios), 3
                    )
                    if truncation_ratios
                    else 0,
                    "max_ratio": round(max(truncation_ratios), 3)
                    if truncation_ratios
                    else 0,
                    "traces_with_truncation": sum(
                        1 for r in truncation_ratios if r > 0
                    ),
                },
            }
        except Exception as e:
            logger.error(f"Failed to compute aggregate stats: {e}")
            return {"error": str(e)}

    async def update_trace_evaluation(
        self, trace_id: str, evaluation_id: str, scores: Dict[str, float]
    ) -> bool:
        """Update a trace with evaluation results (called by background eval)."""
        trace = await self.get_trace(trace_id)
        if not trace:
            return False

        trace.evaluation_id = evaluation_id
        trace.evaluation_scores = scores
        return await self.store_trace(trace)


# Module-level singleton
diagnostics_store = DiagnosticsStore()
