"""
Search Orchestrator Service

Coordinates multi-source search execution with parallel
processing, fusion, reranking, and caching.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import (
    SearchExecutor,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSource,
)
from .cache import SearchCache
from .fusion import ResultFusion
from .metrics import SearchMetrics
from .reranker import SearchReranker

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the search orchestrator."""

    # Timeout for individual executor calls
    executor_timeout: float = 5.0

    # Whether to continue if some executors fail
    allow_partial_results: bool = True

    # Minimum executors that must succeed
    min_successful_executors: int = 1

    # Whether to use caching
    enable_cache: bool = True

    # Whether to rerank results
    enable_rerank: bool = True

    # Minimum results needed for reranking
    min_results_for_rerank: int = 5


class SearchOrchestrator:
    """
    Coordinates multi-source search execution.

    Features:
    - Parallel execution across vector, graph, and keyword sources
    - Result fusion using RRF
    - Optional Cohere reranking
    - Caching for improved performance
    - Comprehensive metrics tracking
    - Graceful degradation on source failures
    """

    def __init__(
        self,
        executors: Optional[List[SearchExecutor]] = None,
        fusion: Optional[ResultFusion] = None,
        reranker: Optional[SearchReranker] = None,
        cache: Optional[SearchCache] = None,
        metrics: Optional[SearchMetrics] = None,
        config: Optional[OrchestratorConfig] = None,
    ):
        """
        Initialize the search orchestrator.

        Args:
            executors: List of search executors (vector, graph, keyword)
            fusion: Result fusion service
            reranker: Reranking service
            cache: Cache service
            metrics: Metrics tracking service
            config: Orchestrator configuration
        """
        self.executors = executors or []
        self.fusion = fusion or ResultFusion()
        self.reranker = reranker or SearchReranker()
        self.cache = cache or SearchCache()
        self.metrics = metrics or SearchMetrics()
        self.config = config or OrchestratorConfig()

    def register_executor(self, executor: SearchExecutor):
        """Register a search executor."""
        self.executors.append(executor)
        logger.info(f"Registered search executor: {executor.source_name.value}")

    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Execute a search across all sources.

        Args:
            query: The search query

        Returns:
            SearchResponse with fused and reranked results
        """
        start_time = time.time()
        cache_hit = False

        # Check cache first
        if self.config.enable_cache:
            cached_results = await self.cache.get(query)
            if cached_results:
                cache_hit = True
                execution_time_ms = (time.time() - start_time) * 1000

                self.metrics.record_search(
                    query=query,
                    results=cached_results,
                    execution_time_ms=execution_time_ms,
                    sources_used=[],
                    cache_hit=True,
                )

                return SearchResponse(
                    results=cached_results,
                    total_count=len(cached_results),
                    query=query,
                    execution_time_ms=execution_time_ms,
                    cache_hit=True,
                )

        # Determine which executors to use
        executors_to_use = self._select_executors(query)

        if not executors_to_use:
            logger.warning("No executors available for search")
            return SearchResponse(
                results=[],
                total_count=0,
                query=query,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Execute searches in parallel
        results_per_source = await self._execute_parallel(query, executors_to_use)

        # Collect all results and track sources used
        all_results = []
        sources_used = []

        for executor, results in zip(executors_to_use, results_per_source):
            if isinstance(results, Exception):
                self.metrics.record_source_failure(executor.source_name, results)
                logger.error(f"Executor {executor.source_name.value} failed: {results}")
            else:
                all_results.extend(results)
                if results:
                    sources_used.append(executor.source_name)

        # Check minimum executor requirement
        if len(sources_used) < self.config.min_successful_executors:
            if not self.config.allow_partial_results:
                error_msg = (
                    f"Only {len(sources_used)} executors succeeded, "
                    f"minimum {self.config.min_successful_executors} required"
                )
                logger.error(error_msg)

                self.metrics.record_search(
                    query=query,
                    results=[],
                    execution_time_ms=(time.time() - start_time) * 1000,
                    sources_used=sources_used,
                    error=error_msg,
                )

                return SearchResponse(
                    results=[],
                    total_count=0,
                    query=query,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    sources_used=sources_used,
                )

        # Fuse results
        fused_results = self.fusion.fuse(all_results)

        # Apply minimum score filter
        if query.min_score > 0:
            fused_results = [r for r in fused_results if r.score >= query.min_score]

        # Rerank if enabled and enough results
        reranked = False
        if (
            self.config.enable_rerank
            and len(fused_results) >= self.config.min_results_for_rerank
        ):
            fused_results = await self.reranker.rerank(
                query.text, fused_results, top_n=query.limit + query.offset
            )
            reranked = True

        # Apply pagination
        final_results = fused_results[query.offset : query.offset + query.limit]

        # Cache results
        if self.config.enable_cache and final_results:
            await self.cache.set(query, final_results)

        execution_time_ms = (time.time() - start_time) * 1000

        # Record metrics
        self.metrics.record_search(
            query=query,
            results=final_results,
            execution_time_ms=execution_time_ms,
            sources_used=sources_used,
            cache_hit=False,
            reranked=reranked,
        )

        # Build response
        response = SearchResponse(
            results=final_results,
            total_count=len(fused_results),
            query=query,
            execution_time_ms=execution_time_ms,
            sources_used=sources_used,
            fusion_metadata={
                "total_raw_results": len(all_results),
                "fused_count": len(fused_results),
                "reranked": reranked,
                "sources_contributed": len(sources_used),
            },
            cache_hit=cache_hit,
        )

        logger.info(
            f"Search completed: {len(final_results)} results from "
            f"{len(sources_used)} sources in {execution_time_ms:.0f}ms"
        )

        return response

    def _select_executors(self, query: SearchQuery) -> List[SearchExecutor]:
        """Select executors based on query configuration."""
        selected = []

        for executor in self.executors:
            # Check availability
            if not executor.is_available:
                continue

            source = executor.source_name

            # Check include filter
            if query.include_sources:
                if source not in query.include_sources:
                    continue

            # Check exclude filter
            if query.exclude_sources:
                if source in query.exclude_sources:
                    continue

            selected.append(executor)

        return selected

    async def _execute_parallel(
        self, query: SearchQuery, executors: List[SearchExecutor]
    ) -> List[List[SearchResult] | Exception]:
        """Execute searches in parallel with timeout handling."""

        async def execute_with_timeout(
            executor: SearchExecutor,
        ) -> List[SearchResult] | Exception:
            try:
                async with asyncio.timeout(self.config.executor_timeout):
                    return await executor.execute(query)
            except asyncio.TimeoutError:
                return TimeoutError(f"Executor {executor.source_name.value} timed out")
            except Exception as e:
                return e

        tasks = [execute_with_timeout(e) for e in executors]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all search components.

        Returns:
            Dictionary with health status for each component
        """
        health = {
            "orchestrator": "healthy",
            "executors": {},
            "cache": self.cache.get_stats(),
            "metrics": self.metrics.get_summary(),
        }

        for executor in self.executors:
            try:
                executor_health = await executor.health_check()
                health["executors"][executor.source_name.value] = executor_health
            except Exception as e:
                health["executors"][executor.source_name.value] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        # Determine overall health
        executor_statuses = [
            h.get("status", "unknown") for h in health["executors"].values()
        ]

        if all(s == "healthy" for s in executor_statuses):
            health["status"] = "healthy"
        elif any(s == "healthy" for s in executor_statuses):
            health["status"] = "degraded"
        else:
            health["status"] = "unhealthy"

        return health

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "metrics": self.metrics.get_summary(),
            "quality": self.metrics.get_quality_metrics(),
            "cache": self.cache.get_stats(),
            "fusion": self.fusion.get_stats(),
            "reranker": self.reranker.get_stats(),
            "executors": [e.source_name.value for e in self.executors],
        }
