"""
Search Reranker Service

Provides reranking capabilities using Cohere or custom scoring
to improve result relevance after initial retrieval.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RerankerConfig:
    """Configuration for the reranker."""

    # Cohere settings
    cohere_model: str = "rerank-english-v3.0"
    cohere_timeout: float = 5.0

    # Minimum results needed to trigger reranking
    min_results_for_rerank: int = 3

    # Maximum results to send to Cohere (cost/latency optimization)
    max_results_to_rerank: int = 50

    # Whether to use async Cohere client
    use_async: bool = True

    # Fallback scoring weights
    fallback_weights: Dict[str, float] = None

    def __post_init__(self):
        if self.fallback_weights is None:
            self.fallback_weights = {
                "original_score": 0.5,
                "source_diversity": 0.2,
                "recency": 0.15,
                "title_match": 0.15,
            }


class BaseReranker(ABC):
    """Abstract base class for rerankers."""

    @abstractmethod
    async def rerank(
        self, query: str, results: List[SearchResult], top_n: Optional[int] = None
    ) -> List[SearchResult]:
        """Rerank results for the given query."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the reranker name."""
        pass


class CohereReranker(BaseReranker):
    """
    Reranks results using Cohere's rerank API.

    Falls back to custom scoring if Cohere is unavailable.
    """

    def __init__(
        self, api_key: Optional[str] = None, config: Optional[RerankerConfig] = None
    ):
        """
        Initialize the Cohere reranker.

        Args:
            api_key: Cohere API key (uses env var if not provided)
            config: Reranker configuration
        """
        self.config = config or RerankerConfig()
        self._client = None
        self._api_key = api_key
        self._is_available = False

        self._init_client()

    def _init_client(self):
        """Initialize the Cohere client."""
        try:
            import cohere

            api_key = self._api_key
            if not api_key:
                import os

                api_key = os.getenv("COHERE_API_KEY")

            if api_key:
                self._client = cohere.AsyncClient(api_key)
                self._is_available = True
                logger.info("Cohere reranker initialized successfully")
            else:
                logger.warning("No Cohere API key found, using fallback reranker")

        except ImportError:
            logger.warning("Cohere package not installed, using fallback reranker")
        except Exception as e:
            logger.error(f"Failed to initialize Cohere client: {e}")

    @property
    def name(self) -> str:
        return "cohere" if self._is_available else "fallback"

    async def rerank(
        self, query: str, results: List[SearchResult], top_n: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Rerank results using Cohere or fallback scoring.

        Args:
            query: The search query
            results: Results to rerank
            top_n: Maximum results to return

        Returns:
            Reranked list of SearchResult objects
        """
        if not results:
            return []

        if len(results) < self.config.min_results_for_rerank:
            return results

        top_n = top_n or len(results)

        if self._is_available and self._client:
            try:
                return await self._cohere_rerank(query, results, top_n)
            except Exception as e:
                logger.warning(f"Cohere rerank failed, using fallback: {e}")
                return await self._fallback_rerank(query, results, top_n)
        else:
            return await self._fallback_rerank(query, results, top_n)

    async def _cohere_rerank(
        self, query: str, results: List[SearchResult], top_n: int
    ) -> List[SearchResult]:
        """Rerank using Cohere API."""
        # Limit results to avoid excessive API costs
        results_to_rerank = results[: self.config.max_results_to_rerank]

        # Prepare documents for Cohere
        documents = [
            f"{r.title}\n{r.snippet}" if r.title else r.snippet
            for r in results_to_rerank
        ]

        try:
            async with asyncio.timeout(self.config.cohere_timeout):
                response = await self._client.rerank(
                    query=query,
                    documents=documents,
                    top_n=min(top_n, len(documents)),
                    model=self.config.cohere_model,
                )
        except asyncio.TimeoutError:
            logger.warning("Cohere rerank timed out")
            raise

        # Map Cohere results back to SearchResult objects
        reranked = []
        for item in response.results:
            original = results_to_rerank[item.index]
            reranked_result = SearchResult(
                document_id=original.document_id,
                score=item.relevance_score,
                snippet=original.snippet,
                title=original.title,
                source=original.source,
                metadata={
                    **original.metadata,
                    "reranker": "cohere",
                    "original_score": original.score,
                    "rerank_index": item.index,
                },
                highlight=original.highlight,
                chunk_id=original.chunk_id,
            )
            reranked.append(reranked_result)

        logger.debug(f"Cohere reranked {len(results)} results to top {len(reranked)}")
        return reranked

    async def _fallback_rerank(
        self, query: str, results: List[SearchResult], top_n: int
    ) -> List[SearchResult]:
        """Fallback reranking using custom scoring."""
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        scored_results = []
        for result in results:
            score = self._calculate_fallback_score(result, query_lower, query_terms)
            scored_results.append((result, score))

        # Sort by fallback score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Create reranked results
        reranked = []
        for result, score in scored_results[:top_n]:
            reranked_result = SearchResult(
                document_id=result.document_id,
                score=score,
                snippet=result.snippet,
                title=result.title,
                source=result.source,
                metadata={
                    **result.metadata,
                    "reranker": "fallback",
                    "original_score": result.score,
                },
                highlight=result.highlight,
                chunk_id=result.chunk_id,
            )
            reranked.append(reranked_result)

        logger.debug(f"Fallback reranked {len(results)} results to top {len(reranked)}")
        return reranked

    def _calculate_fallback_score(
        self, result: SearchResult, query_lower: str, query_terms: set
    ) -> float:
        """Calculate fallback score for a result."""
        weights = self.config.fallback_weights
        score = 0.0

        # Original score contribution
        score += weights["original_score"] * result.score

        # Source diversity bonus
        source_count = result.metadata.get("source_count", 1)
        diversity_bonus = min(source_count / 3, 1.0)
        score += weights["source_diversity"] * diversity_bonus

        # Title match bonus
        title_lower = result.title.lower() if result.title else ""
        title_term_overlap = len(query_terms & set(title_lower.split()))
        title_bonus = min(title_term_overlap / max(len(query_terms), 1), 1.0)
        score += weights["title_match"] * title_bonus

        # Recency bonus (if available)
        # This would need timestamp in metadata
        score += weights["recency"] * 0.5  # Default middle score

        return min(score, 1.0)


class SearchReranker:
    """
    Main reranker service that manages multiple reranking strategies.

    Provides a unified interface for reranking with automatic
    fallback and circuit breaker support.
    """

    def __init__(
        self,
        cohere_api_key: Optional[str] = None,
        config: Optional[RerankerConfig] = None,
    ):
        """
        Initialize the search reranker.

        Args:
            cohere_api_key: Optional Cohere API key
            config: Reranker configuration
        """
        self.config = config or RerankerConfig()
        self._cohere_reranker = CohereReranker(cohere_api_key, self.config)

        self._stats = {
            "total_reranks": 0,
            "cohere_reranks": 0,
            "fallback_reranks": 0,
            "errors": 0,
        }

    async def rerank(
        self, query: str, results: List[SearchResult], top_n: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Rerank results for the given query.

        Args:
            query: The search query
            results: Results to rerank
            top_n: Maximum results to return

        Returns:
            Reranked list of SearchResult objects
        """
        try:
            reranked = await self._cohere_reranker.rerank(query, results, top_n)
            self._stats["total_reranks"] += 1

            if reranked and reranked[0].metadata.get("reranker") == "cohere":
                self._stats["cohere_reranks"] += 1
            else:
                self._stats["fallback_reranks"] += 1

            return reranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            self._stats["errors"] += 1
            # Return original results on error
            return results

    def get_stats(self) -> Dict[str, Any]:
        """Get reranker statistics."""
        return {
            **self._stats,
            "cohere_available": self._cohere_reranker._is_available,
        }

    def reset_stats(self):
        """Reset reranker statistics."""
        self._stats = {
            "total_reranks": 0,
            "cohere_reranks": 0,
            "fallback_reranks": 0,
            "errors": 0,
        }
