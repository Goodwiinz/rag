"""
Shared Pydantic models for all services
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, validator


# Enums
class ContentType(str, Enum):
    """Content type enum"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class SearchType(str, Enum):
    """Search type enum"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    HYBRID = "hybrid"


class EmbeddingModel(str, Enum):
    """Embedding model enum"""
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    CLIP_VIT_BASE_PATCH32 = "clip-vit-base-patch32"
    WAV2VEC2_BASE = "wav2vec2-base"
    SENTENCE_TRANSFORMERS = "sentence-transformers"


class InteractionType(str, Enum):
    """User interaction type enum"""
    VIEW = "view"
    LIKE = "like"
    BOOKMARK = "bookmark"
    SHARE = "share"
    DOWNLOAD = "download"
    COMMENT = "comment"


# Base models
class BaseSchema(BaseModel):
    """Base schema with common fields"""
    class Config:
        orm_mode = True
        validate_assignment = True
        use_enum_values = True


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields"""
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# User models
class UserBase(BaseSchema):
    """Base user model"""
    email: EmailStr = Field(..., description="User email")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    is_active: bool = Field(True, description="Whether user is active")


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8, description="Password")

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseSchema):
    """User update model"""
    username: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(UserBase, TimestampSchema):
    """User response model"""
    id: UUID = Field(..., description="User ID")


# Authentication models
class Token(BaseSchema):
    """JWT token model"""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseSchema):
    """Token data model"""
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    scopes: List[str] = []


class LoginRequest(BaseSchema):
    """Login request model"""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class RefreshTokenRequest(BaseSchema):
    """Refresh token request model"""
    refresh_token: str = Field(..., description="Refresh token")


# Content models
class ContentBase(BaseSchema):
    """Base content model"""
    title: str = Field(..., max_length=500, description="Content title")
    description: Optional[str] = Field(None, description="Content description")
    content_type: ContentType = Field(..., description="Content type")
    file_url: Optional[str] = Field(None, description="File URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    checksum: Optional[str] = Field(None, description="File checksum")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Content metadata")
    is_public: bool = Field(False, description="Whether content is public")
    is_processed: bool = Field(False, description="Whether content is processed")


class ContentCreate(ContentBase):
    """Content creation model"""
    tags: Optional[List[str]] = Field(None, description="Content tags")


class ContentUpdate(BaseSchema):
    """Content update model"""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class ContentResponse(ContentBase, TimestampSchema):
    """Content response model"""
    id: UUID = Field(..., description="Content ID")
    user_id: UUID = Field(..., description="Owner user ID")
    processed_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list, description="Content tags")
    owner: Optional[Dict[str, Any]] = None


# Specialized content models
class TextContentResponse(ContentResponse):
    """Text content response model"""
    text_content: Optional[str] = None
    word_count: Optional[int] = None
    language: Optional[str] = None
    reading_time_minutes: Optional[int] = None


class ImageContentResponse(ContentResponse):
    """Image content response model"""
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    color_space: Optional[str] = None
    has_transparency: Optional[bool] = None
    dominant_colors: Optional[List[str]] = None


class AudioContentResponse(ContentResponse):
    """Audio content response model"""
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_rate: Optional[int] = None
    format: Optional[str] = None
    transcription: Optional[str] = None
    transcription_language: Optional[str] = None
    transcription_confidence: Optional[float] = None


class VideoContentResponse(ContentResponse):
    """Video content response model"""
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    bit_rate: Optional[int] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None


# Search models
class SearchFilters(BaseSchema):
    """Search filters model"""
    content_type: Optional[List[ContentType]] = None
    user_id: Optional[UUID] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None
    date_range: Optional[Dict[str, datetime]] = None
    file_size_range: Optional[Dict[str, int]] = None
    language: Optional[str] = None


class SearchWeights(BaseSchema):
    """Search weights model for hybrid search"""
    text: float = Field(0.33, ge=0, le=1, description="Text search weight")
    semantic: float = Field(0.33, ge=0, le=1, description="Semantic search weight")
    visual: float = Field(0.34, ge=0, le=1, description="Visual search weight")

    @validator('visual')
    def validate_weights_sum(cls, v, values):
        if 'text' in values and 'semantic' in values:
            total = values['text'] + values['semantic'] + v
            if abs(total - 1.0) > 0.01:
                raise ValueError('Weights must sum to 1.0')
        return v


class SearchRequest(BaseSchema):
    """Search request model"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    search_type: SearchType = Field(..., description="Search type")
    filters: Optional[SearchFilters] = None
    weights: Optional[SearchWeights] = None
    similarity_threshold: float = Field(0.5, ge=0, le=1, description="Similarity threshold")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    sort_by: str = Field("relevance", description="Sort by field")
    sort_order: str = Field("desc", description="Sort order")
    include_metadata: bool = Field(True, description="Include metadata in results")


class SearchResult(BaseSchema):
    """Search result model"""
    id: UUID = Field(..., description="Content ID")
    title: str = Field(..., description="Content title")
    description: Optional[str] = None
    content_type: ContentType = Field(..., description="Content type")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score")
    metadata: Optional[Dict[str, Any]] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: datetime = Field(..., description="Creation timestamp")
    tags: List[str] = Field(default_factory=list, description="Content tags")
    owner: Optional[Dict[str, Any]] = None


class SearchResponse(BaseSchema):
    """Search response model"""
    search_id: UUID = Field(..., description="Search ID")
    query: str = Field(..., description="Original query")
    search_type: SearchType = Field(..., description="Search type")
    results: List[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    suggestions: Optional[List[str]] = None
    facets: Optional[Dict[str, Any]] = None


# File upload models
class FileUploadRequest(BaseSchema):
    """File upload request model"""
    content_type: ContentType = Field(..., description="Content type")
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = Field(False, description="Whether content is public")
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class FileUploadResponse(BaseSchema):
    """File upload response model"""
    upload_id: UUID = Field(..., description="Upload ID")
    upload_url: str = Field(..., description="Upload URL")
    expires_at: datetime = Field(..., description="Upload URL expiration")


class ProcessingStatus(BaseSchema):
    """Processing status model"""
    status: str = Field(..., description="Processing status")
    progress: float = Field(0, ge=0, le=1, description="Progress percentage")
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Analytics models
class SearchAnalytics(BaseSchema):
    """Search analytics model"""
    search_count: int
    avg_response_time_ms: float
    click_rate: float
    popular_queries: List[Dict[str, Any]]


# Error response models
class ErrorResponse(BaseSchema):
    """Error response model"""
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None


# Pagination models
class PaginationParams(BaseSchema):
    """Pagination parameters model"""
    limit: int = Field(20, ge=1, le=100, description="Page size")
    offset: int = Field(0, ge=0, description="Page offset")


class PaginatedResponse(BaseSchema):
    """Paginated response model"""
    items: List[Any]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool