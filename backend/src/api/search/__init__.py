"""
Search API routes for search, knowledge graph, and search quality.

The Qdrant-backed ``/api/v1/vectors`` router was removed with the Qdrant→DO KB
migration — it had no consumer and no working backend (see
docs/database/ADR-qdrant-dense-leg.md).

The experimental ``/api/v1/multi-agent-search`` (+ ``/api/v2``) routers were
retired the same way — no frontend/CLI/script caller ever hit them (the app
uses ``/search/`` + ``/search/hybrid``). Restore with ``git revert`` if needed.
"""

from .knowledge_graph import router as knowledge_graph_router
from .search import router as search_router
from .search_quality import router as search_quality_router

__all__ = [
    "search_router",
    "search_quality_router",
    "knowledge_graph_router",
]
