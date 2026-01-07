"""
Search Services Module

This module provides a modular, testable search architecture that supports:
- Multi-source search (vector, graph, keyword)
- Result fusion using Reciprocal Rank Fusion (RRF)
- Cohere/custom reranking
- Search metrics and analytics
- Caching

Components:
- SearchOrchestrator: Coordinates multi-source search execution
- ResultFusion: Fuses results from multiple sources
- SearchReranker: Reranks results using Cohere or custom scoring
- SearchMetrics: Tracks search performance and analytics
- SearchCache: Caches search results for improved performance
"""

from .base import (
    SearchExecutor,
    SearchQuery,
    SearchResult,
    SearchSource,
)
from .cache import SearchCache
from .fusion import ResultFusion
from .metrics import SearchMetrics
from .orchestrator import SearchOrchestrator
from .reranker import SearchReranker

__all__ = [
    # Base types
    "SearchQuery",
    "SearchResult",
    "SearchExecutor",
    "SearchSource",
    # Services
    "SearchOrchestrator",
    "ResultFusion",
    "SearchReranker",
    "SearchMetrics",
    "SearchCache",
]
