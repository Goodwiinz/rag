"""
Search API routes for search, vectors, knowledge graph, and multi-agent search
"""

from .search import router as search_router
from .search_quality import router as search_quality_router
from .vectors import router as vectors_router
from .knowledge_graph import router as knowledge_graph_router
from .multi_agent_search import router as multi_agent_search_router
from .multi_agent_search_v2 import router as multi_agent_search_v2_router

__all__ = [
    "search_router",
    "search_quality_router",
    "vectors_router",
    "knowledge_graph_router",
    "multi_agent_search_router",
    "multi_agent_search_v2_router",
]
