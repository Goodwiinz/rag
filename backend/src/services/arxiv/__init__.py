"""
ArXiv integration services

Lazy loading to avoid import errors from missing optional dependencies.
"""

def get_arxiv_service():
    """Get ArXivIngestionService lazily."""
    from .arxiv_service import ArXivIngestionService
    return ArXivIngestionService

def get_arxiv_change_tracker():
    """Get ArXivChangeTracker lazily."""
    from .arxiv_change_tracker import ArXivChangeTracker
    return ArXivChangeTracker

def get_arxiv_search_service():
    """Get ArxivSearchService lazily."""
    from .arxiv_search_service import ArxivSearchService
    return ArxivSearchService

def get_arxiv_kg_integration():
    """Get ArxivKGIntegration lazily."""
    from .arxiv_kg_integration import ArxivKGIntegration
    return ArxivKGIntegration

__all__ = [
    "get_arxiv_service",
    "get_arxiv_change_tracker",
    "get_arxiv_search_service",
    "get_arxiv_kg_integration",
]
