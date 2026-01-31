"""
Vector database models and schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import Base


class VectorCollectionType(str, Enum):
    """Vector collection types"""

    DOCUMENT_CHUNKS = "document_chunks"
    ENTITIES = "entities"
    IMAGES = "images"
    AUDIO_TRANSCRIPTIONS = "audio_transcriptions"
    VIDEO_FRAMES = "video_frames"


class VectorMetadata(BaseModel):
    """Metadata for vector entries"""

    document_id: Optional[str] = None
    organization_id: Optional[str] = None
    content_type: str
    source_type: str  # text, image, audio, video
    chunk_index: Optional[int] = None
    entity_type: Optional[str] = None
    confidence_score: Optional[float] = None
    timestamp: datetime
    additional_data: Optional[Dict[str, Any]] = None


class VectorEntry(BaseModel):
    """Vector entry for database storage"""

    id: str
    vector: List[float]
    text: Optional[str] = None
    metadata: VectorMetadata
    collection: VectorCollectionType


class VectorSearchRequest(BaseModel):
    """Vector search request"""

    query: str
    collection: VectorCollectionType
    organization_id: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None


class VectorSearchResult(BaseModel):
    """Vector search result"""

    id: str
    text: Optional[str] = None
    score: float
    metadata: VectorMetadata
    document_id: Optional[str] = None


class VectorSearchResponse(BaseModel):
    """Vector search response"""

    results: List[VectorSearchResult]
    total_found: int
    search_time: float
    query: str
    collection: VectorCollectionType


class EmbeddingRequest(BaseModel):
    """Text embedding request"""

    text: str
    model: Optional[str] = None
    provider: Optional[str] = None  # "azure_openai" or "sentence_transformers"


class EmbeddingResponse(BaseModel):
    """Text embedding response"""

    embedding: List[float]
    model: str
    dimension: int
    processing_time: float
    provider: Optional[str] = None


class BatchEmbeddingRequest(BaseModel):
    """Batch text embedding request"""

    texts: List[str]
    model: Optional[str] = None
    provider: Optional[str] = None  # "azure_openai" or "sentence_transformers"


class BatchEmbeddingResponse(BaseModel):
    """Batch text embedding response"""

    embeddings: List[List[float]]
    model: str
    dimension: int
    processing_time: float
    failed_count: int
    errors: List[Dict[str, Any]] = []
    provider: Optional[str] = None


class CollectionConfig(BaseModel):
    """Vector collection configuration"""

    name: str
    vector_size: int
    distance: str = "Cosine"  # Cosine, Euclidean, Dot
    on_disk: bool = True
    hnsw_config: Optional[Dict[str, Any]] = None
    quantization_config: Optional[Dict[str, Any]] = None


class CollectionStats(BaseModel):
    """Vector collection statistics"""

    name: str
    vectors_count: int
    indexed_vectors_count: int
    points_count: int
    segments_count: int
    disk_data_size: int
    ram_data_size: int
    config: Dict[str, Any]


class VectorOperationResult(BaseModel):
    """Result of vector operation"""

    success: bool
    operation_id: Optional[str] = None
    message: str
    error: Optional[str] = None
    processing_time: float


class VectorHealthStatus(BaseModel):
    """Vector database health status"""

    status: str  # healthy, degraded, unhealthy
    collections_count: int
    total_vectors: int
    disk_usage_mb: float
    ram_usage_mb: float
    uptime_seconds: int
    version: str
