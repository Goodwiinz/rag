"""
Knowledge graph data models and schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


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
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in entity detection"
    )
    extraction_method: ExtractionMethod = Field(
        ..., description="How entity was extracted"
    )
    position: Optional[List[int]] = Field(
        None, description="Position in source text [start, end]"
    )
    context: Optional[str] = Field(None, description="Context around entity")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional entity metadata"
    )
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class CreateEntityRequest(BaseModel):
    """Request model for creating entities"""

    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    confidence_score: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence in entity detection"
    )
    extraction_method: ExtractionMethod = Field(
        default=ExtractionMethod.SPACY_NER, description="How entity was extracted"
    )
    position: Optional[List[int]] = Field(
        None, description="Position in source text [start, end]"
    )
    context: Optional[str] = Field(None, description="Context around entity")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional entity metadata"
    )
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    organization_id: Optional[str] = Field(
        None,
        description="Owning organization; stamped on the node for direct tenant "
        "scoping (avoids the org-doc-id IN-list).",
    )


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


class PaginatedEntitiesResponse(BaseModel):
    """Paginated response for entity listings"""

    entities: List[EntityResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class UpdateEntityRequest(BaseModel):
    """Request model for updating entities"""

    name: Optional[str] = Field(None, description="Updated entity name")
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Updated confidence score"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


# Relationship Models
class Relationship(BaseModel):
    """Base relationship model"""

    id: str = Field(..., description="Unique relationship identifier")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    strength: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relationship strength"
    )
    confidence_score: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence in relationship"
    )
    context: Optional[str] = Field(
        None, description="Context where relationship was found"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Evidence supporting relationship"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional relationship metadata"
    )
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class CreateRelationshipRequest(BaseModel):
    """Request model for creating relationships"""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    strength: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relationship strength"
    )
    confidence_score: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence in relationship"
    )
    context: Optional[str] = Field(
        None, description="Context where relationship was found"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Evidence supporting relationship"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional relationship metadata"
    )
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


# Graph Search Models
class GraphSearchRequest(BaseModel):
    """Request model for graph-based searches"""

    query: str = Field(..., description="Search query")
    entity_types: Optional[List[EntityType]] = Field(
        None, description="Filter by entity types"
    )
    relationship_types: Optional[List[RelationshipType]] = Field(
        None, description="Filter by relationship types"
    )
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum traversal depth")
    max_results: int = Field(
        default=50, ge=1, le=200, description="Maximum number of results"
    )
    min_strength: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Minimum relationship strength"
    )
    include_metadata: bool = Field(
        default=True, description="Include entity/relationship metadata"
    )
    document_id_filter: Optional[str] = Field(
        None, description="Filter by specific document"
    )


class GraphPath(BaseModel):
    """Model representing a path in the graph"""

    entities: List[EntityResponse] = Field(..., description="Entities in the path")
    relationships: List[RelationshipResponse] = Field(
        ..., description="Relationships connecting entities"
    )
    total_strength: float = Field(..., description="Combined strength of the path")
    path_length: int = Field(..., description="Number of relationships in path")
    confidence_score: float = Field(..., description="Overall confidence in path")


class GraphSearchResponse(BaseModel):
    """Response model for graph searches"""

    query: str
    entities: List[EntityResponse] = Field(
        default_factory=list, description="Found entities"
    )
    relationships: List[RelationshipResponse] = Field(
        default_factory=list, description="Found relationships"
    )
    paths: List[GraphPath] = Field(
        default_factory=list, description="Found paths between entities"
    )
    total_entities: int = Field(default=0, description="Total number of entities found")
    total_relationships: int = Field(
        default=0, description="Total number of relationships found"
    )
    total_paths: int = Field(default=0, description="Total number of paths found")
    search_time: float = Field(..., description="Time taken for search in seconds")


# Document Processing Models
class DocumentEntityExtraction(BaseModel):
    """Model for entity extraction from documents"""

    document_id: str
    entities: List[Entity] = Field(
        default_factory=list, description="Extracted entities"
    )
    relationships: List[Relationship] = Field(
        default_factory=list, description="Extracted relationships"
    )
    processing_time: float = Field(
        default=0.0, description="Processing time in seconds"
    )
    confidence_threshold: float = Field(
        default=0.7, description="Minimum confidence for inclusion"
    )


class BatchEntityRequest(BaseModel):
    """Request for batch entity operations"""

    entities: List[CreateEntityRequest] = Field(..., description="Entities to create")
    relationships: List[CreateRelationshipRequest] = Field(
        default_factory=list, description="Relationships to create"
    )
    upsert: bool = Field(
        default=False, description="Whether to update existing entities"
    )
    document_id: Optional[str] = Field(None, description="Source document ID")


class BatchEntityResponse(BaseModel):
    """Response for batch entity operations"""

    created_entities: List[EntityResponse] = Field(default_factory=list)
    updated_entities: List[EntityResponse] = Field(default_factory=list)
    created_relationships: List[RelationshipResponse] = Field(default_factory=list)
    updated_relationships: List[RelationshipResponse] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time: float = Field(default=0.0)


# Graph Analytics Models
class GraphAnalytics(BaseModel):
    """Model for graph analytics and statistics"""

    total_entities: int = Field(default=0, description="Total number of entities")
    total_relationships: int = Field(
        default=0, description="Total number of relationships"
    )
    entity_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count by entity type"
    )
    relationship_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count by relationship type"
    )
    average_degree: float = Field(default=0.0, description="Average node degree")
    connected_components: int = Field(
        default=0, description="Number of connected components"
    )
    largest_component_size: int = Field(
        default=0, description="Size of largest connected component"
    )
    clustering_coefficient: float = Field(
        default=0.0, description="Average clustering coefficient"
    )


class GraphHealthStatus(BaseModel):
    """Model for graph database health status"""

    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    neo4j_version: str = Field(..., description="Neo4j version")
    database_size: Optional[str] = Field(None, description="Database size")
    node_count: int = Field(default=0, description="Total number of nodes")
    relationship_count: int = Field(
        default=0, description="Total number of relationships"
    )
    index_count: int = Field(default=0, description="Number of indexes")
    constraint_count: int = Field(default=0, description="Number of constraints")
    uptime: Optional[str] = Field(None, description="Database uptime")
    last_error: Optional[str] = Field(None, description="Last error message")
    response_time_ms: float = Field(
        ..., description="Database response time in milliseconds"
    )


# Graph Visualization Models
class GraphVisualizationNode(BaseModel):
    """Node model for graph visualization"""

    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    x: Optional[float] = Field(None, description="X coordinate for layout")
    y: Optional[float] = Field(None, description="Y coordinate for layout")
    size: Optional[int] = Field(None, description="Node size for visualization")
    color: Optional[str] = Field(None, description="Node color")


class GraphVisualizationEdge(BaseModel):
    """Edge model for graph visualization"""

    id: str
    source: str
    target: str
    type: str
    weight: float = Field(default=1.0)
    properties: Dict[str, Any] = Field(default_factory=dict)
    width: Optional[float] = Field(None, description="Edge width for visualization")
    color: Optional[str] = Field(None, description="Edge color")


class GraphVisualizationData(BaseModel):
    """Complete graph data for visualization"""

    nodes: List[GraphVisualizationNode] = Field(default_factory=list)
    edges: List[GraphVisualizationEdge] = Field(default_factory=list)
    layout: str = Field(default="force", description="Layout algorithm")
    metadata: Dict[str, Any] = Field(default_factory=dict)
