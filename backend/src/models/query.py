"""
Query-related data models for the RAG system
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class QueryIntent(str, Enum):
    """Query intent enumeration"""
    FACTUAL_LOOKUP = "factual_lookup"
    REASONING = "reasoning"
    COMPARISON = "comparison"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    DEFINITIONAL = "definitional"
    PROCEDURAL = "procedural"
    ANALYTICAL = "analytical"
    EXPLORATORY = "exploratory"
    SUMMARIZATION = "summarization"


class QueryComplexity(str, Enum):
    """Query complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class QueryStatus(str, Enum):
    """Query processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryEntity(BaseModel):
    """Named entity extracted from a query"""
    text: str = Field(..., description="The entity text")
    label: str = Field(..., description="Entity label (PERSON, ORG, etc.)")
    start: int = Field(..., description="Start position in query")
    end: int = Field(..., description="End position in query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    type: str = Field(..., description="Entity type")
    description: Optional[str] = Field(None, description="Entity description")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")

    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")
        return v


class QueryAnalysis(BaseModel):
    """Complete query analysis result"""
    original_query: str = Field(..., description="Original query text")
    normalized_query: str = Field(..., description="Normalized query text")
    intent: QueryIntent = Field(..., description="Classified intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent confidence")
    complexity: QueryComplexity = Field(..., description="Query complexity")
    entities: List[QueryEntity] = Field(default_factory=list, description="Extracted entities")
    keywords: List[str] = Field(default_factory=list, description="Important keywords")
    expanded_terms: List[str] = Field(default_factory=list, description="Query expansion terms")
    language: str = Field(..., description="Detected language code")
    sentiment: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Sentiment score")
    temporal_expressions: List[str] = Field(default_factory=list, description="Temporal expressions")
    numerical_values: List[Dict[str, Any]] = Field(default_factory=list, description="Numerical values")
    processing_time_ms: float = Field(0.0, ge=0.0, description="Processing time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")
        return v

    @validator('processing_time_ms')
    def validate_processing_time(cls, v):
        if v < 0:
            raise ValueError("Processing time cannot be negative")
        return v


class QueryRequest(BaseModel):
    """Query request model"""
    query: str = Field(..., min_length=1, max_length=2000, description="The search query")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    session_id: Optional[str] = Field(None, description="Session ID")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    language_hint: Optional[str] = Field(None, description="Language hint")
    enable_expansion: bool = Field(True, description="Enable query expansion")
    max_expansion_terms: int = Field(10, ge=1, le=50, description="Maximum expansion terms")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Search filters")
    limit: int = Field(10, ge=1, le=100, description="Result limit")
    offset: int = Field(0, ge=0, description="Result offset")

    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    """Query response model"""
    id: UUID = Field(default_factory=uuid4, description="Query ID")
    status: QueryStatus = Field(..., description="Query status")
    analysis: Optional[QueryAnalysis] = Field(None, description="Query analysis results")
    results: Optional[List[Any]] = Field(None, description="Search results")
    total_results: int = Field(0, ge=0, description="Total number of results")
    processing_time_ms: float = Field(0.0, ge=0.0, description="Total processing time")
    cached: bool = Field(False, description="Whether result was cached")
    suggestions: List[str] = Field(default_factory=list, description="Query suggestions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class QueryHistory(BaseModel):
    """Query history model"""
    id: UUID = Field(default_factory=uuid4, description="History entry ID")
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="Query text")
    intent: QueryIntent = Field(..., description="Query intent")
    results_count: int = Field(0, ge=0, description="Number of results")
    clicked_results: List[str] = Field(default_factory=list, description="Clicked result IDs")
    satisfaction_score: Optional[float] = Field(None, ge=1.0, le=5.0, description="User satisfaction")
    processing_time_ms: float = Field(0.0, ge=0.0, description="Processing time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class QueryFeedback(BaseModel):
    """Query feedback model"""
    query_id: UUID = Field(..., description="Query ID")
    user_id: str = Field(..., description="User ID")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5)")
    helpful: bool = Field(..., description="Was the result helpful?")
    comments: Optional[str] = Field(None, max_length=1000, description="User comments")
    result_positions: List[int] = Field(default_factory=list, description="Clicked result positions")
    session_duration_ms: Optional[float] = Field(None, ge=0.0, description="Session duration")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class QueryPattern(BaseModel):
    """Query pattern model for analytics"""
    pattern: str = Field(..., description="Query pattern")
    frequency: int = Field(..., ge=0, description="Pattern frequency")
    intent_distribution: Dict[QueryIntent, float] = Field(..., description="Intent distribution")
    avg_results_count: float = Field(..., ge=0.0, description="Average results count")
    avg_satisfaction: Optional[float] = Field(None, ge=1.0, le=5.0, description="Average satisfaction")
    last_seen: datetime = Field(..., description="Last seen timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QueryAnalytics(BaseModel):
    """Query analytics model"""
    total_queries: int = Field(..., ge=0, description="Total number of queries")
    unique_queries: int = Field(..., ge=0, description="Number of unique queries")
    avg_query_length: float = Field(..., ge=0.0, description="Average query length")
    top_intents: List[Dict[str, Any]] = Field(..., description="Top query intents")
    top_keywords: List[Dict[str, Any]] = Field(..., description="Top keywords")
    intent_distribution: Dict[QueryIntent, float] = Field(..., description="Intent distribution")
    complexity_distribution: Dict[QueryComplexity, float] = Field(..., description="Complexity distribution")
    language_distribution: Dict[str, float] = Field(..., description="Language distribution")
    avg_processing_time_ms: float = Field(..., ge=0.0, description="Average processing time")
    cache_hit_rate: float = Field(..., ge=0.0, le=1.0, description="Cache hit rate")
    satisfaction_rate: float = Field(..., ge=0.0, le=1.0, description="Satisfaction rate")
    period_start: datetime = Field(..., description="Analytics period start")
    period_end: datetime = Field(..., description="Analytics period end")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }