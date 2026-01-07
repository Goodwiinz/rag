"""
Result Fusion Service

Implements Reciprocal Rank Fusion (RRF) to combine results
from multiple search sources into a unified ranked list.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from .base import SearchResult, SearchSource

logger = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    """Configuration for result fusion."""

    # RRF constant (typically 60)
    rrf_k: int = 60

    # Source weights for weighted RRF
    source_weights: Dict[SearchSource, float] = None

    # Minimum number of sources for a result to be included
    min_sources: int = 1

    # Whether to boost results appearing in multiple sources
    multi_source_boost: float = 1.2

    def __post_init__(self):
        if self.source_weights is None:
            self.source_weights = {
                SearchSource.VECTOR: 0.4,
                SearchSource.GRAPH: 0.35,
                SearchSource.KEYWORD: 0.25,
            }


class ResultFusion:
    """
    Fuses results from multiple search sources using Reciprocal Rank Fusion.

    RRF score = sum(weight_i / (k + rank_i)) for each source i

    This approach:
    - Combines rankings without requiring score normalization
    - Handles missing results gracefully
    - Weights sources by reliability/relevance
    """

    def __init__(self, config: Optional[FusionConfig] = None):
        """
        Initialize the fusion service.

        Args:
            config: Fusion configuration options
        """
        self.config = config or FusionConfig()
        self._fusion_stats = {
            "total_fusions": 0,
            "avg_results_per_fusion": 0.0,
            "source_contributions": defaultdict(int),
        }

    def fuse(
        self, results: List[SearchResult], deduplicate: bool = True
    ) -> List[SearchResult]:
        """
        Fuse results from multiple sources using RRF.

        Args:
            results: List of results from all sources
            deduplicate: Whether to deduplicate by document_id

        Returns:
            Fused and ranked list of SearchResult objects
        """
        if not results:
            return []

        # Group results by source for RRF calculation
        results_by_source: Dict[SearchSource, List[SearchResult]] = defaultdict(list)
        for r in results:
            results_by_source[r.source].append(r)

        # Sort each source's results by score to get rankings
        for source in results_by_source:
            results_by_source[source].sort(key=lambda x: x.score, reverse=True)

        # Calculate RRF scores
        doc_scores: Dict[str, Dict] = defaultdict(
            lambda: {
                "rrf_score": 0.0,
                "result": None,
                "sources": [],
                "ranks": {},
            }
        )

        k = self.config.rrf_k

        for source, source_results in results_by_source.items():
            weight = self.config.source_weights.get(source, 0.3)

            for rank, result in enumerate(source_results, 1):
                doc_id = result.document_id

                # RRF contribution: weight / (k + rank)
                rrf_contribution = weight * (1 / (k + rank))
                doc_scores[doc_id]["rrf_score"] += rrf_contribution
                doc_scores[doc_id]["sources"].append(source)
                doc_scores[doc_id]["ranks"][source.value] = rank

                # Keep the best result object (highest original score)
                if (
                    doc_scores[doc_id]["result"] is None
                    or result.score > doc_scores[doc_id]["result"].score
                ):
                    doc_scores[doc_id]["result"] = result

        # Apply multi-source boost
        if self.config.multi_source_boost > 1.0:
            for doc_id, data in doc_scores.items():
                if len(data["sources"]) >= 2:
                    data["rrf_score"] *= self.config.multi_source_boost

        # Filter by min_sources
        filtered_docs = {
            doc_id: data
            for doc_id, data in doc_scores.items()
            if len(data["sources"]) >= self.config.min_sources
        }

        # Sort by RRF score
        sorted_docs = sorted(
            filtered_docs.items(), key=lambda x: x[1]["rrf_score"], reverse=True
        )

        # Create fused results
        fused_results = []
        for doc_id, data in sorted_docs:
            original = data["result"]

            fused_result = SearchResult(
                document_id=doc_id,
                score=data["rrf_score"],
                snippet=original.snippet,
                title=original.title,
                source=SearchSource.FUSED,
                metadata={
                    **original.metadata,
                    "fusion_sources": [s.value for s in data["sources"]],
                    "source_ranks": data["ranks"],
                    "original_score": original.score,
                    "source_count": len(data["sources"]),
                },
                highlight=original.highlight,
                chunk_id=original.chunk_id,
            )
            fused_results.append(fused_result)

        # Update stats
        self._update_stats(results_by_source, len(fused_results))

        logger.debug(
            f"Fused {len(results)} results from {len(results_by_source)} sources "
            f"into {len(fused_results)} unique results"
        )

        return fused_results

    def _update_stats(
        self,
        results_by_source: Dict[SearchSource, List[SearchResult]],
        fused_count: int,
    ):
        """Update internal fusion statistics."""
        self._fusion_stats["total_fusions"] += 1

        # Running average of results per fusion
        n = self._fusion_stats["total_fusions"]
        prev_avg = self._fusion_stats["avg_results_per_fusion"]
        self._fusion_stats["avg_results_per_fusion"] = (
            prev_avg + (fused_count - prev_avg) / n
        )

        # Track source contributions
        for source, results in results_by_source.items():
            self._fusion_stats["source_contributions"][source.value] += len(results)

    def get_stats(self) -> Dict:
        """Get fusion statistics."""
        return {
            "total_fusions": self._fusion_stats["total_fusions"],
            "avg_results_per_fusion": round(
                self._fusion_stats["avg_results_per_fusion"], 2
            ),
            "source_contributions": dict(self._fusion_stats["source_contributions"]),
        }

    def reset_stats(self):
        """Reset fusion statistics."""
        self._fusion_stats = {
            "total_fusions": 0,
            "avg_results_per_fusion": 0.0,
            "source_contributions": defaultdict(int),
        }
