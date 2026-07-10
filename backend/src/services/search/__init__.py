"""
Search Services Module

Base search types shared across search implementations (see base.py).
The orchestrator/fusion/reranker/cache/metrics pipeline that used to live
here had zero live construction sites and was removed.
"""

from .base import SearchExecutor, SearchQuery, SearchResult, SearchSource

__all__ = [
    # Base types
    "SearchQuery",
    "SearchResult",
    "SearchExecutor",
    "SearchSource",
]
