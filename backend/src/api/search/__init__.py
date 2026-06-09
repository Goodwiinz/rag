"""
Search API routes for search, knowledge graph, and multi-agent search

The Qdrant-backed ``/api/v1/vectors`` router was removed with the Qdrant→DO KB
migration — it had no consumer and no working backend (see
docs/database/ADR-qdrant-dense-leg.md).
"""

from .knowledge_graph import router as knowledge_graph_router
from .multi_agent_search import router as multi_agent_search_router
from .multi_agent_search_v2 import router as multi_agent_search_v2_router
from .search import router as search_router
from .search_quality import router as search_quality_router

__all__ = [
    "search_router",
    "search_quality_router",
    "knowledge_graph_router",
    "multi_agent_search_router",
    "multi_agent_search_v2_router",
]
