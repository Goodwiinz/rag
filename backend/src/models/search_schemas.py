"""
Search API schemas and models for full-text search functionality
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .document import DocumentType


class SearchType(str, Enum):
    """Search types"""

    FULLTEXT = "fulltext"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    VECTOR = "vector"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    GRAPH = "graph"


class SearchSortOrder(str, Enum):
    """Search result sort orders"""

    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"


class SearchFilter(BaseModel):
    """Search filters"""

    document_ids: Optional[List[str]] = Field(
        None, description="Filter by selected document IDs"
    )
    document_types: Optional[List[DocumentType]] = Field(
        None, description="Filter by document types"
    )
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    date_from: Optional[datetime] = Field(
        None, description="Filter documents from this date"
    )
    date_to: Optional[datetime] = Field(
        None, description="Filter documents to this date"
    )
    file_size_min: Optional[int] = Field(None, description="Minimum file size in bytes")
    file_size_max: Optional[int] = Field(None, description="Maximum file size in bytes")
    organization_id: Optional[str] = Field(None, description="Filter by organization")
    uploaded_by_user_id: Optional[str] = Field(
        None, description="Filter by uploading user"
    )
    is_public: Optional[bool] = Field(None, description="Filter by public status")


class SearchQuery(BaseModel):
    """Search query request"""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    search_type: SearchType = Field(SearchType.FULLTEXT, description="Type of search")
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum number of results"
    )
    offset: int = Field(default=0, ge=0, description="Results offset for pagination")
    sort_order: SearchSortOrder = Field(
        SearchSortOrder.RELEVANCE, description="Sort order"
    )
    filters: Optional[SearchFilter] = Field(None, description="Search filters")
    include_snippets: bool = Field(
        default=True, description="Include text snippets with highlights"
    )
    snippet_length: int = Field(
        default=200, ge=50, le=500, description="Length of text snippets"
    )
    highlight_tags: tuple = Field(
        default=("mark", "/mark"), description="HTML tags for highlighting"
    )
    synthesize_answer: bool = Field(
        default=False, description="Generate LLM-synthesized answer from results"
    )


class TextSnippet(BaseModel):
    """Text snippet with highlighting"""

    text: str = Field(..., description="Snippet text with highlights")
    start_position: int = Field(..., description="Start position in original text")
    end_position: int = Field(..., description="End position in original text")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Relevance score for this snippet"
    )


class SearchResult(BaseModel):
    """Individual search result"""

    document_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    document_type: DocumentType = Field(..., description="Document type")
    content_preview: str = Field(..., description="Content preview")
    snippets: List[TextSnippet] = Field(
        default_factory=list, description="Relevant text snippets"
    )
    relevance_score: float = Field(..., ge=0.0, description="Overall relevance score")
    file_size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last update date")
    processing_status: str = Field(..., description="Processing status")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    is_public: bool = Field(..., description="Whether document is public")
    uploaded_by_user_id: str = Field(..., description="ID of user who uploaded")
    organization_id: str = Field(..., description="Organization ID")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )


class DeterministicTrace(BaseModel):
    """Deterministic trace metadata for response auditing"""

    decision_trace_id: str = Field(..., description="Deterministic decision trace ID")


class SearchResponse(BaseModel):
    """Search response with results and metadata"""

    query: str = Field(..., description="Original search query")
    search_id: str = Field(..., description="Unique identifier for this search")
    search_type: SearchType = Field(..., description="Type of search performed")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., ge=0, description="Total number of results")
    returned_results: int = Field(..., ge=0, description="Number of results returned")
    search_time_ms: float = Field(..., description="Search time in milliseconds")
    limit: int = Field(..., description="Results limit used")
    offset: int = Field(..., description="Results offset used")
    has_more: bool = Field(..., description="Whether more results are available")
    suggestions: Optional[List[str]] = Field(None, description="Search suggestions")
    filters_applied: Optional[Dict[str, Any]] = Field(
        None, description="Applied filters"
    )
    answer_type: Optional[str] = Field(
        None, description="Deterministic answer strategy used"
    )
    claims: List[str] = Field(
        default_factory=list, description="Deterministic extracted claims"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Deterministic answer confidence"
    )
    coverage: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Deterministic evidence coverage"
    )
    decision_trace_id: Optional[str] = Field(
        None, description="Deterministic decision trace identifier"
    )
    trace: Optional[DeterministicTrace] = Field(
        None, description="Deterministic trace object"
    )
    deterministic_status: Optional[str] = Field(
        None,
        description="Deterministic gate status (SUPPORTED, INSUFFICIENT_EVIDENCE, CONFLICTING_EVIDENCE, NO_MATCH)",
    )
    deterministic_message: Optional[str] = Field(
        None, description="Deterministic gate explanation"
    )
    synthesized_answer: Optional[str] = Field(
        None, description="LLM-synthesized answer from retrieved context"
    )


class SearchSuggestion(BaseModel):
    """Search suggestion"""

    text: str = Field(..., description="Suggestion text")
    type: str = Field(
        ..., description="Suggestion type (completion, correction, expansion)"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SearchAnalytics(BaseModel):
    """Search analytics data"""

    total_searches: int = Field(..., description="Total number of searches")
    average_search_time_ms: float = Field(..., description="Average search time")
    most_common_queries: List[Dict[str, Any]] = Field(
        ..., description="Most common search queries"
    )
    search_types_distribution: Dict[str, int] = Field(
        ..., description="Distribution of search types"
    )
    zero_result_queries: List[str] = Field(
        ..., description="Queries that returned no results"
    )
    average_results_per_search: float = Field(
        ..., description="Average number of results per search"
    )


class SearchIndex(BaseModel):
    """Search index information"""

    name: str = Field(..., description="Index name")
    type: str = Field(..., description="Index type")
    document_count: int = Field(..., description="Number of indexed documents")
    size_mb: float = Field(..., description="Index size in MB")
    last_updated: datetime = Field(..., description="Last update time")
    is_active: bool = Field(..., description="Whether index is active")
    configuration: Dict[str, Any] = Field(..., description="Index configuration")


class SearchConfig(BaseModel):
    """Search configuration"""

    min_query_length: int = Field(default=2, description="Minimum query length")
    max_query_length: int = Field(default=1000, description="Maximum query length")
    default_limit: int = Field(default=20, description="Default result limit")
    max_limit: int = Field(default=100, description="Maximum result limit")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    enable_fuzzy_search: bool = Field(default=True, description="Enable fuzzy search")
    enable_stemming: bool = Field(default=True, description="Enable stemming")
    enable_phonetic_search: bool = Field(
        default=False, description="Enable phonetic search"
    )
    highlight_pre_tag: str = Field(default="<mark>", description="Highlight start tag")
    highlight_post_tag: str = Field(default="</mark>", description="Highlight end tag")
    snippet_max_words: int = Field(default=40, description="Maximum words in snippet")
    snippet_surround: int = Field(
        default=50, description="Words around match in snippet"
    )
