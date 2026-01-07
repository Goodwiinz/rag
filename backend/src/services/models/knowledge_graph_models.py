"""
Knowledge Graph Service Models
Reusing and extending existing graph models for microservice architecture
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class EntityType(str, Enum):
    """Entity types that can be stored in the knowledge graph"""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    DATE = "DATE"
    FINANCIAL = "FINANCIAL"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    URL = "URL"
    JOB_TITLE = "JOB_TITLE"
    CONCEPT = "CONCEPT"
    DOCUMENT = "DOCUMENT"
    TOPIC = "TOPIC"
    TECHNOLOGY = "TECHNOLOGY"
    RESEARCH = "RESEARCH"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    """Relationship types between entities"""
    WORKS_FOR = "WORKS_FOR"
    KNOWS = "KNOWS"
    RELATED_TO = "RELATED_TO"
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"
    MENTIONED_IN = "MENTIONED_IN"
    APPEARS_WITH = "APPEARS_WITH"
    CREATED_BY = "CREATED_BY"
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    COLLABORATES_WITH = "COLLABORATES_WITH"
    REPORTS_TO = "REPORTS_TO"
    MEMBER_OF = "MEMBER_OF"
    ATTENDED = "ATTENDED"
    SPOKE_AT = "SPOKE_AT"
    PUBLISHED_BY = "PUBLISHED_BY"
    CITED = "CITED"
    REFERENCES = "REFERENCES"
    CUSTOM = "CUSTOM"


class ExtractionMethod(str, Enum):
    """Methods used for entity and relationship extraction"""
    SPACY_NER = "spacy_ner"
    PATTERN_MATCHING = "pattern_matching"
    MANUAL = "manual"
    LLM_EXTRACTION = "llm_extraction"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"  # Default for None or unknown extraction methods


# Entity Models
class Entity(BaseModel):
    """Base entity model"""
    id: str = Field(..., description="Unique entity identifier")
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in entity detection")
    extraction_method: ExtractionMethod = Field(..., description="How entity was extracted")
    position: Optional[List[int]] = Field(None, description="Position in source text [start, end]")
    context: Optional[str] = Field(None, description="Context around entity")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional entity metadata")
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for multi-tenancy")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class CreateEntityRequest(BaseModel):
    """Request model for creating entities"""
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence in entity detection")
    extraction_method: ExtractionMethod = Field(default=ExtractionMethod.SPACY_NER, description="How entity was extracted")
    position: Optional[List[int]] = Field(None, description="Position in source text [start, end]")
    context: Optional[str] = Field(None, description="Context around entity")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional entity metadata")
    source_document_id: Optional[str] = Field(None, description="Source document ID")


class EntityResponse(BaseModel):
    """Response model for entity data"""
    id: str
    name: str
    entity_type: EntityType
    confidence_score: float
    extraction_method: ExtractionMethod
    position: Optional[List[int]]
    context: Optional[str]
    metadata: Dict[str, Any]
    source_document_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class UpdateEntityRequest(BaseModel):
    """Request model for updating entities"""
    name: Optional[str] = Field(None, description="Updated entity name")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Updated confidence score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


# Relationship Models
class Relationship(BaseModel):
    """Base relationship model"""
    id: str = Field(..., description="Unique relationship identifier")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence in relationship")
    context: Optional[str] = Field(None, description="Context where relationship was found")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting relationship")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional relationship metadata")
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for multi-tenancy")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class CreateRelationshipRequest(BaseModel):
    """Request model for creating relationships"""
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence in relationship")
    context: Optional[str] = Field(None, description="Context where relationship was found")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting relationship")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional relationship metadata")
    source_document_id: Optional[str] = Field(None, description="Source document ID")


class RelationshipResponse(BaseModel):
    """Response model for relationship data"""
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    strength: float
    confidence_score: float
    context: Optional[str]
    evidence: List[str]
    metadata: Dict[str, Any]
    source_document_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# Batch Operations Models
class BatchEntityRequest(BaseModel):
    """Request for batch entity operations"""
    entities: List[CreateEntityRequest] = Field(..., description="Entities to create")
    relationships: List[CreateRelationshipRequest] = Field(default_factory=list, description="Relationships to create")
    upsert: bool = Field(default=False, description="Whether to update existing entities")
    document_id: Optional[str] = Field(None, description="Source document ID")


class BatchEntityResponse(BaseModel):
    """Response for batch entity operations"""
    created_entities: List[EntityResponse] = Field(default_factory=list)
    updated_entities: List[EntityResponse] = Field(default_factory=list)
    created_relationships: List[RelationshipResponse] = Field(default_factory=list)
    updated_relationships: List[RelationshipResponse] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time: float = Field(default=0.0)


# Search Models
class EntitySearchRequest(BaseModel):
    """Request model for entity search"""
    query: str = Field(..., description="Search query")
    entity_types: Optional[List[EntityType]] = Field(None, description="Filter by entity types")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    include_metadata: bool = Field(default=True, description="Include metadata in results")


class EntitySearchResponse(BaseModel):
    """Response model for entity search"""
    entities: List[EntityResponse] = Field(default_factory=list, description="Found entities")
    total_count: int = Field(default=0, description="Total number of matching entities")
    query: str = Field(..., description="Original search query")
    search_time: float = Field(default=0.0, description="Time taken for search in seconds")


# Entity Neighborhood Models
class EntityNeighborhoodRequest(BaseModel):
    """Request model for getting entity neighborhood"""
    entity_id: str = Field(..., description="Central entity ID")
    depth: int = Field(default=2, ge=1, le=5, description="Neighborhood depth")
    max_nodes: int = Field(default=50, ge=1, le=200, description="Maximum nodes to include")
    min_strength: float = Field(default=0.1, ge=0.0, le=1.0, description="Minimum relationship strength")
    entity_types: Optional[List[EntityType]] = Field(None, description="Filter by entity types")
    relationship_types: Optional[List[RelationshipType]] = Field(None, description="Filter by relationship types")


class EntityNeighborhoodResponse(BaseModel):
    """Response model for entity neighborhood"""
    central_entity: EntityResponse = Field(..., description="Central entity")
    entities: List[EntityResponse] = Field(default_factory=list, description="Related entities")
    relationships: List[RelationshipResponse] = Field(default_factory=list, description="Relationships")
    total_nodes: int = Field(default=0, description="Total nodes in neighborhood")
    total_edges: int = Field(default=0, description="Total edges in neighborhood")
    depth: int = Field(default=0, description="Actual depth explored")


# WebSocket Event Models
class WebSocketEvent(BaseModel):
    """WebSocket event model"""
    type: str = Field(..., description="Event type")
    tenant_id: str = Field(..., description="Tenant ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")


class EntityUpdateEvent(WebSocketEvent):
    """Entity update event"""
    type: str = "entity_updated"
    entity: EntityResponse = Field(..., description="Updated entity")


class RelationshipUpdateEvent(WebSocketEvent):
    """Relationship update event"""
    type: str = "relationship_updated"
    relationship: RelationshipResponse = Field(..., description="Updated relationship")


# Service Health Models
class ServiceHealth(BaseModel):
    """Service health model"""
    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    service: str = Field(..., description="Service name")
    port: int = Field(..., description="Service port")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    neo4j: str = Field(..., description="Neo4j connection status")
    redis: str = Field(..., description="Redis connection status")
    postgresql: str = Field(..., description="PostgreSQL connection status")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


# Metrics Models
class ServiceMetrics(BaseModel):
    """Service metrics model"""
    entity_count: int = Field(default=0, description="Total number of entities")
    relationship_count: int = Field(default=0, description="Total number of relationships")
    active_websockets: int = Field(default=0, description="Number of active WebSocket connections")
    avg_response_time: float = Field(default=0.0, description="Average API response time in ms")
    cache_hit_rate: float = Field(default=0.0, description="Cache hit rate (0-1)")
    error_rate: float = Field(default=0.0, description="Error rate (0-1)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")