"""
Base types and interfaces for the search module.

Provides foundational data classes and abstract base classes
for implementing search executors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SearchSource(str, Enum):
    """Enumeration of search sources."""

    VECTOR = "vector"
    GRAPH = "graph"
    KEYWORD = "keyword"
    FUSED = "fused"


@dataclass
class SearchQuery:
    """
    Represents a search query with all necessary parameters.

    Attributes:
        text: The search query text
        filters: Dictionary of filters to apply (e.g., {"file_type": "pdf"})
        limit: Maximum number of results to return
        offset: Number of results to skip (for pagination)
        user_id: Optional user ID for personalization
        organization_id: Optional organization ID for multi-tenancy
        include_sources: List of sources to include (default: all)
        exclude_sources: List of sources to exclude
        min_score: Minimum score threshold for results
        metadata: Additional query metadata
    """

    text: str
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 10
    offset: int = 0
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    include_sources: Optional[List[SearchSource]] = None
    exclude_sources: Optional[List[SearchSource]] = None
    min_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate query parameters."""
        if self.limit < 1:
            raise ValueError("limit must be at least 1")
        if self.limit > 100:
            raise ValueError("limit cannot exceed 100")
        if self.offset < 0:
            raise ValueError("offset cannot be negative")
        if self.min_score < 0.0 or self.min_score > 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0")


@dataclass
class SearchResult:
    """
    Represents a single search result.

    Attributes:
        document_id: Unique identifier of the document
        score: Relevance score (0.0 to 1.0)
        snippet: Text snippet containing the match
        title: Document title
        source: Which search source returned this result
        metadata: Additional result metadata (file_type, created_at, etc.)
        highlight: Optional highlighted text with match markers
        chunk_id: Optional chunk identifier for chunked documents
        rank: Optional rank in the original result set
    """

    document_id: str
    score: float
    snippet: str
    title: str = ""
    source: SearchSource = SearchSource.VECTOR
    metadata: Dict[str, Any] = field(default_factory=dict)
    highlight: Optional[str] = None
    chunk_id: Optional[str] = None
    rank: Optional[int] = None

    def __post_init__(self):
        """Validate result parameters."""
        if self.score < 0.0:
            self.score = 0.0
        if self.score > 1.0:
            self.score = 1.0


@dataclass
class SearchResponse:
    """
    Complete search response with results and metadata.

    Attributes:
        results: List of search results
        total_count: Total number of matching documents
        query: Original search query
        execution_time_ms: Time taken to execute search
        sources_used: List of sources that contributed results
        fusion_metadata: Metadata about result fusion
        cache_hit: Whether results were served from cache
    """

    results: List[SearchResult]
    total_count: int
    query: SearchQuery
    execution_time_ms: float = 0.0
    sources_used: List[SearchSource] = field(default_factory=list)
    fusion_metadata: Dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SearchExecutor(ABC):
    """
    Abstract base class for search executors.

    Implementations should handle searching a specific source
    (vector store, knowledge graph, keyword index, etc.)
    """

    @abstractmethod
    async def execute(self, query: SearchQuery) -> List[SearchResult]:
        """
        Execute a search query against this source.

        Args:
            query: The search query to execute

        Returns:
            List of SearchResult objects

        Raises:
            SearchExecutionError: If the search fails
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> SearchSource:
        """Return the source type for this executor."""
        pass

    @property
    def is_available(self) -> bool:
        """
        Check if this executor is currently available.

        Override in subclasses to implement health checks.
        """
        return True

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on this executor.

        Returns:
            Dictionary with health status information
        """
        return {
            "source": self.source_name.value,
            "available": self.is_available,
            "status": "healthy" if self.is_available else "unavailable",
        }
