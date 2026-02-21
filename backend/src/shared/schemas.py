"""
Shared schemas for microservices communication
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


class BaseResponse(BaseModel):
    """Base response model"""

    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model"""

    success: bool = False
    error_code: str
    error_type: str
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


class PaginationRequest(BaseModel):
    """Pagination request parameters"""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: Optional[int] = Field(
        default=None, ge=0, description="Override calculated offset"
    )


class PaginationResponse(BaseModel):
    """Pagination response information"""

    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseResponse):
    """Paginated response wrapper"""

    data: List[Any]
    pagination: PaginationResponse


# Document Enums
class DocumentType(str, Enum):
    """Document types for different modalities"""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MULTIMODAL = "multimodal"


class ProcessingStatus(str, Enum):
    """Processing status for documents"""

    QUEUED = "queued"
    UPLOADING = "uploading"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchType(str, Enum):
    """Search types"""

    HYBRID = "hybrid"
    VECTOR = "vector"
    GRAPH = "graph"
    KEYWORD = "keyword"


class QueryIntent(str, Enum):
    """Query intent classification"""

    LOOKUP = "lookup"
    REASONING = "reasoning"
    COMPARISON = "comparison"
    TEMPORAL = "temporal"
    CAUSAL = "causal"


class UserRole(str, Enum):
    """User roles"""

    ADMIN = "admin"
    CONTENT_MANAGER = "content_manager"
    USER = "user"
    ANALYST = "analyst"
    VIEWER = "viewer"


class NotificationType(str, Enum):
    """Notification types"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SUCCESS = "success"


# Document Schemas
class DocumentMetadata(BaseModel):
    """Document metadata"""

    title: str
    filename: str
    file_size_bytes: int
    mime_type: str
    document_type: DocumentType
    tags: Optional[List[str]] = []
    is_public: bool = False
    custom_metadata: Optional[Dict[str, Any]] = {}

    @validator("file_size_bytes")
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError("File size must be positive")
        return v


class DocumentResponse(BaseModel):
    """Document response model"""

    id: UUID
    title: str
    filename: str
    document_type: DocumentType
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    processing_status: ProcessingStatus
    tags: Optional[List[str]] = Field(default_factory=list)
    is_public: bool
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    content_preview: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    """Detailed document response"""

    content_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    processing_error: Optional[str] = None
    processing_retry_count: int = 0
    uploaded_by_user: Optional[Dict[str, Any]] = None


class ProcessingStatusResponse(BaseModel):
    """Processing status response"""

    document_id: UUID
    status: ProcessingStatus
    current_stage: str
    progress_percentage: float = Field(ge=0, le=100)
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


# Search Schemas
class SearchFilters(BaseModel):
    """Search filters"""

    document_types: Optional[List[DocumentType]] = None
    date_range: Optional[Dict[str, datetime]] = None
    tags: Optional[List[str]] = None
    file_size_range: Optional[Dict[str, float]] = None
    organization_id: Optional[UUID] = None
    user_id: Optional[UUID] = None


class SearchRequest(BaseModel):
    """Search request"""

    query: str = Field(min_length=1, max_length=1000)
    search_type: SearchType = SearchType.HYBRID
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    include_metadata: bool = True
    sort_by: str = Field(default="relevance", pattern="^(relevance|date|title)$")


class MatchedContent(BaseModel):
    """Matched content piece"""

    content: str
    content_type: str
    relevance_score: float = Field(ge=0, le=1)
    source_reference: Optional[str] = None


class SearchResult(BaseModel):
    """Single search result"""

    document_id: UUID
    title: str
    content_snippet: str
    relevance_score: float = Field(ge=0, le=1)
    document_type: DocumentType
    matched_content: List[MatchedContent]
    metadata: Optional[Dict[str, Any]] = {}


class QueryClassification(BaseModel):
    """Query classification result"""

    intent: QueryIntent
    confidence: float = Field(ge=0, le=1)
    entities: List[Dict[str, Any]] = []


class SearchResponse(BaseModel):
    """Search response"""

    query: str
    search_id: UUID
    total_results: int
    search_time_ms: float
    results: List[SearchResult]
    facets: Optional[Dict[str, Any]] = {}
    query_classification: Optional[QueryClassification] = None


class SearchSuggestion(BaseModel):
    """Search suggestion"""

    text: str
    type: str = Field(pattern="^(autocomplete|correction|expansion)$")
    score: float = Field(ge=0, le=1)


# Knowledge Graph Schemas
class Entity(BaseModel):
    """Entity model"""

    id: UUID
    name: str
    type: str
    confidence: float = Field(ge=0, le=1)
    document_count: int
    connection_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class EntityDetail(Entity):
    """Detailed entity information"""

    description: Optional[str] = None
    aliases: List[str] = []
    attributes: Dict[str, Any] = {}
    related_entities: List[Dict[str, Any]] = []
    temporal_data: Optional[Dict[str, Any]] = {}


class RelatedEntity(BaseModel):
    """Related entity information"""

    entity: Entity
    relationship_type: str
    relationship_strength: float = Field(ge=0, le=1)
    context_snippets: List[str] = []


class GraphNode(BaseModel):
    """Graph node for visualization"""

    id: str
    label: str
    type: str
    size: float
    color: str
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    """Graph edge for visualization"""

    source: str
    target: str
    label: str
    weight: float
    strength: float = Field(ge=0, le=1)


class GraphData(BaseModel):
    """Knowledge graph data for visualization"""

    nodes: List[GraphNode]
    edges: List[GraphEdge]
    layout: Dict[str, Any] = {}
    statistics: Dict[str, Any] = {}


# Evaluation Schemas
class RAGTriadMetrics(BaseModel):
    """RAG Triad evaluation metrics"""

    answer_relevancy: Dict[str, Any]
    faithfulness: Dict[str, Any]
    contextual_relevancy: Dict[str, Any]


class QualityMetrics(BaseModel):
    """Content quality metrics"""

    coherence: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    conciseness: float = Field(ge=0, le=1)
    hallucination_rate: float = Field(ge=0, le=1)
    source_diversity: float = Field(ge=0, le=1)


class QueryPerformanceMetrics(BaseModel):
    """Query performance metrics"""

    total_latency_ms: float
    search_latency_ms: float
    generation_latency_ms: float
    retrieval_count: int
    model_tokens_used: Dict[str, int]
    cache_hit_rate: float = Field(ge=0, le=1)


class EvaluationRequest(BaseModel):
    """Evaluation request"""

    query_id: Optional[UUID] = None
    question: str
    answer: str
    retrieved_context: List[Dict[str, Any]]
    ground_truth: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Evaluation response"""

    query_id: Optional[UUID] = None
    evaluation_id: UUID
    rag_triad: RAGTriadMetrics
    quality_metrics: QualityMetrics
    performance_metrics: QueryPerformanceMetrics
    generated_at: datetime


class BenchmarkRequest(BaseModel):
    """Benchmark request"""

    benchmark_type: str = Field(pattern="^(rag_triad|performance|stress|scalability)$")
    test_dataset: str
    parameters: Dict[str, Any] = {}


# Processing Pipeline Schemas
class ProcessingJobRequest(BaseModel):
    """Processing job request"""

    document_id: UUID
    processing_options: Dict[str, Any] = {
        "extract_entities": True,
        "generate_embeddings": True,
        "extract_metadata": True,
        "ocr_enabled": True,
        "transcription_enabled": True,
    }


class ProcessingStage(BaseModel):
    """Processing stage information"""

    name: str
    status: ProcessingStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    output_metadata: Optional[Dict[str, Any]] = {}
    error_message: Optional[str] = None


class ProcessingJob(BaseModel):
    """Processing job model"""

    id: UUID
    document_id: UUID
    status: ProcessingStatus
    current_stage: str
    progress_percentage: float = Field(ge=0, le=100)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProcessingJobDetail(ProcessingJob):
    """Detailed processing job information"""

    stages: List[ProcessingStage]
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    processing_metadata: Dict[str, Any] = {}


# User Management Schemas
class LoginRequest(BaseModel):
    """Login request"""

    email: str = Field(pattern="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    """Login response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class TokenRequest(BaseModel):
    """Token refresh request"""

    refresh_token: str


class TokenResponse(BaseModel):
    """Token response"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CreateUserRequest(BaseModel):
    """Create user request"""

    email: str = Field(pattern="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.USER
    organization_id: UUID


class UpdateUserRequest(BaseModel):
    """Update user request"""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    """User response"""

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    organization_id: UUID
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response"""

    storage_quota_mb: int
    storage_used_mb: float
    preferences: Dict[str, Any] = {}
    permissions: List[str] = []


# Analytics Schemas
class UsageStatistics(BaseModel):
    """Usage statistics"""

    time_range: str
    granularity: str
    metrics: Dict[str, Any]
    trend_data: List[Dict[str, Any]]


class PerformanceAnalytics(BaseModel):
    """Performance analytics"""

    service_name: str
    time_range: str
    metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class DashboardWidget(BaseModel):
    """Dashboard widget"""

    widget_id: str
    type: str = Field(pattern="^(metric_chart|table|gauge|alert_list)$")
    title: str
    data: Dict[str, Any]
    position: Dict[str, int]


class DashboardData(BaseModel):
    """Dashboard data"""

    dashboard_id: str
    title: str
    widgets: List[DashboardWidget]
    last_updated: datetime


# WebSocket Schemas
class WebSocketMessage(BaseModel):
    """WebSocket message base"""

    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcessingStatusUpdate(WebSocketMessage):
    """Processing status update WebSocket message"""

    type: str = "processing_status_update"
    data: Dict[str, Any] = {
        "document_id": None,
        "job_id": None,
        "status": None,
        "current_stage": None,
        "progress_percentage": 0,
        "estimated_completion": None,
        "error_message": None,
    }


class SearchProgressUpdate(WebSocketMessage):
    """Search progress update WebSocket message"""

    type: str = "search_progress"
    data: Dict[str, Any] = {
        "search_id": None,
        "stage": None,
        "progress_percentage": 0,
        "intermediate_results": [],
    }


class SystemNotification(WebSocketMessage):
    """System notification WebSocket message"""

    type: str = "system_notification"
    data: Dict[str, Any] = {
        "notification_id": None,
        "notification_type": None,
        "title": None,
        "message": None,
        "actions": [],
    }


# Health Check Schemas
class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(pattern="^(healthy|unhealthy|degraded)$")
    version: str
    environment: str
    timestamp: datetime
    services: Dict[str, Dict[str, Any]] = {}
    uptime_seconds: float


# Rate Limiting Schemas
class RateLimitInfo(BaseModel):
    """Rate limit information"""

    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


# Multi-tenant Schemas
class OrganizationContext(BaseModel):
    """Organization context for requests"""

    organization_id: UUID
    user_role: UserRole
    permissions: List[str]
    storage_quota_mb: int
    storage_used_mb: float


# API Versioning
class APIVersion(BaseModel):
    """API version information"""

    version: str
    deprecated: bool = False
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    migration_guide: Optional[str] = None


# Configuration Schemas
class ServiceConfig(BaseModel):
    """Service configuration"""

    service_name: str
    version: str
    port: int
    host: str = "localhost"
    debug: bool = False
    max_workers: int = 1
    timeout_seconds: int = 30


# Metrics Schemas
class MetricPoint(BaseModel):
    """Single metric data point"""

    timestamp: datetime
    value: float
    labels: Dict[str, str] = {}


class MetricSeries(BaseModel):
    """Time series metric data"""

    name: str
    description: str
    unit: str
    points: List[MetricPoint]
