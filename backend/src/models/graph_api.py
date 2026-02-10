"""
Knowledge Graph API Data Models for Frontend-Graph Communication
Corrected architecture with backend-first graph processing
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, validator


class GraphAlgorithmType(str, Enum):
    """Types of graph algorithms supported by backend"""

    DEGREE_CENTRALITY = "degree_centrality"
    BETWEENNESS_CENTRALITY = "betweenness_centrality"
    CLOSENESS_CENTRALITY = "closeness_centrality"
    EIGENVECTOR_CENTRALITY = "eigenvector_centrality"
    PAGERANK = "pagerank"
    CLUSTERING_COEFFICIENT = "clustering_coefficient"
    COMMUNITY_DETECTION = "community_detection"
    SHORTEST_PATH = "shortest_path"
    SIMILARITY = "similarity"
    RECOMMENDATION = "recommendation"


class CommunityDetectionAlgorithm(str, Enum):
    """Community detection algorithms"""

    LOUVAIN = "louvain"
    LABEL_PROPAGATION = "label_propagation"
    LEIDEN = "leiden"
    INFOMAP = "infomap"


class LayoutAlgorithm(str, Enum):
    """Graph layout algorithms for visualization"""

    FORCE_DIRECTED = "force"
    CIRCULAR = "circular"
    HIERARCHICAL = "hierarchical"
    GRID = "grid"
    RADIAL = "radial"
    CONCENTRIC = "concentric"


class EntityType(str, Enum):
    """Enhanced entity types for knowledge graph"""

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
    TECHNOLOGY = "TECHNOLOGY"
    METRIC = "METRIC"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    """Enhanced relationship types"""

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
    SIMILAR_TO = "SIMILAR_TO"
    PRECEDES = "PRECEDES"
    FOLLOWS = "FOLLOWS"
    CONTAINS = "CONTAINS"
    DEPENDS_ON = "DEPENDS_ON"
    INFLUENCES = "INFLUENCES"
    CUSTOM = "CUSTOM"


# Request Models
class GraphAlgorithmRequest(BaseModel):
    """Request model for graph algorithm execution"""

    algorithm_type: GraphAlgorithmType = Field(
        ..., description="Type of algorithm to execute"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Algorithm-specific parameters"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters to apply to graph data"
    )
    entity_types: Optional[List[EntityType]] = Field(
        None, description="Filter by entity types"
    )
    relationship_types: Optional[List[RelationshipType]] = Field(
        None, description="Filter by relationship types"
    )
    organization_id: str = Field(..., description="Organization ID for multi-tenancy")
    asynchronous: bool = Field(default=True, description="Run asynchronously")
    cache_results: bool = Field(default=True, description="Cache computation results")


class CentralityRequest(GraphAlgorithmRequest):
    """Request model for centrality computation"""

    algorithm_type: GraphAlgorithmType = Field(
        ...,
        regex="^(degree_centrality|betweenness_centrality|closeness_centrality|eigenvector_centrality|pagerank)$",
    )
    include_weights: bool = Field(
        default=True, description="Include edge weights in computation"
    )
    normalization: str = Field(default="standard", description="Normalization method")
    top_n: Optional[int] = Field(None, description="Return only top N results")


class CommunityDetectionRequest(GraphAlgorithmRequest):
    """Request model for community detection"""

    algorithm_type: GraphAlgorithmType = Field(
        default=GraphAlgorithmType.COMMUNITY_DETECTION
    )
    community_algorithm: CommunityDetectionAlgorithm = Field(
        default=CommunityDetectionAlgorithm.LOUVAIN
    )
    resolution: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Community resolution parameter"
    )
    min_community_size: int = Field(
        default=5, ge=1, description="Minimum community size"
    )
    include_overlapping: bool = Field(
        default=False, description="Allow overlapping communities"
    )


class PathfindingRequest(GraphAlgorithmRequest):
    """Request model for pathfinding algorithms"""

    algorithm_type: GraphAlgorithmType = Field(default=GraphAlgorithmType.SHORTEST_PATH)
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    max_depth: int = Field(default=5, ge=1, le=10, description="Maximum path length")
    weight_property: str = Field(default="strength", description="Edge weight property")
    find_all_paths: bool = Field(
        default=False, description="Find all paths, not just shortest"
    )
    max_paths: int = Field(
        default=10, ge=1, description="Maximum number of paths to return"
    )


class GraphVisualizationRequest(BaseModel):
    """Request model for graph visualization data"""

    entity_ids: Optional[List[str]] = Field(
        None, description="Specific entities to include"
    )
    center_entity_id: Optional[str] = Field(
        None, description="Entity to center the view on"
    )
    depth: int = Field(
        default=2, ge=1, le=5, description="Neighborhood depth for expansion"
    )
    max_nodes: int = Field(
        default=100, ge=1, le=1000, description="Maximum number of nodes"
    )
    layout_algorithm: LayoutAlgorithm = Field(default=LayoutAlgorithm.FORCE_DIRECTED)
    layout_options: Dict[str, Any] = Field(
        default_factory=dict, description="Layout algorithm options"
    )
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    include_analytics: bool = Field(default=True, description="Include analytics data")
    organization_id: str = Field(..., description="Organization ID")


# Entity Models
class GraphEntity(BaseModel):
    """Enhanced entity model for graph operations"""

    id: str = Field(..., description="Entity ID")
    name: str = Field(..., description="Entity name")
    canonical_name: str = Field(..., description="Standardized entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    subtypes: List[str] = Field(default_factory=list, description="Entity subtypes")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    importance_score: Optional[float] = Field(
        None, description="Computed importance score"
    )
    description: Optional[str] = Field(None, description="Entity description")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional properties"
    )
    extraction_method: str = Field(..., description="How entity was extracted")
    extraction_context: Optional[str] = Field(None, description="Extraction context")
    first_seen: datetime = Field(..., description="First appearance timestamp")
    last_seen: datetime = Field(..., description="Last appearance timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    source_document_ids: List[str] = Field(
        default_factory=list, description="Source documents"
    )
    organization_id: str = Field(..., description="Organization ID")

    # Graph analytics (computed by backend)
    centrality_metrics: Optional[Dict[str, float]] = Field(
        None, description="Centrality metrics"
    )
    community_info: Optional[Dict[str, Any]] = Field(
        None, description="Community information"
    )
    graph_analytics: Optional[Dict[str, Any]] = Field(
        None, description="Additional graph analytics"
    )


class GraphRelationship(BaseModel):
    """Enhanced relationship model for graph operations"""

    id: str = Field(..., description="Relationship ID")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Relationship type")
    subtype: Optional[str] = Field(None, description="Specific relationship subtype")
    strength: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relationship strength"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )
    weight: float = Field(default=1.0, description="Algorithm weight")
    direction: str = Field(
        default="bidirectional", description="Relationship direction"
    )
    temporal_data: Optional[Dict[str, Any]] = Field(
        None, description="Time-based information"
    )
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    context: Optional[str] = Field(None, description="Relationship context")
    extraction_method: str = Field(..., description="Extraction method")
    source_document_id: Optional[str] = Field(None, description="Source document")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    organization_id: str = Field(..., description="Organization ID")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional properties"
    )

    # Graph analytics
    graph_analytics: Optional[Dict[str, Any]] = Field(
        None, description="Graph analytics data"
    )


# Analytics Models
class CentralityResult(BaseModel):
    """Result of centrality computation"""

    entity_id: str = Field(..., description="Entity ID")
    entity_name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    centrality_score: float = Field(..., description="Centrality score")
    rank: int = Field(..., description="Rank among all entities")
    percentile: float = Field(..., description="Percentile (0-100)")
    confidence: float = Field(..., description="Confidence in computation")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class CommunityResult(BaseModel):
    """Result of community detection"""

    community_id: str = Field(..., description="Community ID")
    entities: List[GraphEntity] = Field(..., description="Entities in community")
    modularity_score: float = Field(..., description="Modularity score")
    size: int = Field(..., description="Community size")
    dominant_entity_type: EntityType = Field(..., description="Most common entity type")
    internal_density: float = Field(..., description="Internal connection density")
    avg_confidence: float = Field(..., description="Average confidence")
    community_metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphPath(BaseModel):
    """Path between entities"""

    path_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Path ID"
    )
    entities: List[GraphEntity] = Field(..., description="Entities in path")
    relationships: List[GraphRelationship] = Field(
        ..., description="Relationships in path"
    )
    total_weight: float = Field(..., description="Total path weight")
    path_length: int = Field(..., description="Number of relationships")
    confidence: float = Field(..., description="Path confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Visualization Models
class GraphLayoutPosition(BaseModel):
    """Position for graph layout"""

    entity_id: str = Field(..., description="Entity ID")
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    z: Optional[float] = Field(None, description="Z coordinate (for 3D layouts)")
    level: Optional[int] = Field(None, description="Hierarchy level")
    cluster: Optional[str] = Field(None, description="Cluster assignment")
    force: Optional[Tuple[float, float]] = Field(None, description="Force vector")


class GraphVisualizationData(BaseModel):
    """Complete visualization data for frontend"""

    entities: List[GraphEntity] = Field(..., description="Entities to visualize")
    relationships: List[GraphRelationship] = Field(
        ..., description="Relationships to visualize"
    )
    layout: Dict[str, GraphLayoutPosition] = Field(..., description="Layout positions")
    layout_algorithm: LayoutAlgorithm = Field(..., description="Layout algorithm used")
    bounds: Dict[str, float] = Field(..., description="Visualization bounds")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Visualization metadata"
    )
    analytics: Optional[Dict[str, Any]] = Field(None, description="Analytics data")
    computed_at: datetime = Field(
        default_factory=datetime.utcnow, description="Computation timestamp"
    )


# Job/Computation Models
class GraphComputationJob(BaseModel):
    """Graph computation job tracking"""

    job_id: str = Field(..., description="Job ID")
    job_type: str = Field(..., description="Job type")
    algorithm: str = Field(..., description="Algorithm used")
    status: str = Field(..., description="Job status")
    progress_percentage: int = Field(default=0, description="Progress percentage")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion"
    )
    input_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Input parameters"
    )
    result_location: Optional[str] = Field(None, description="Result location")
    error_message: Optional[str] = Field(None, description="Error message")
    computation_time_ms: Optional[int] = Field(
        None, description="Computation time in ms"
    )
    user_id: Optional[str] = Field(None, description="User who initiated job")
    organization_id: str = Field(..., description="Organization ID")


# Response Models
class GraphAlgorithmResponse(BaseModel):
    """Response for graph algorithm execution"""

    success: bool = Field(..., description="Success status")
    job_id: Optional[str] = Field(None, description="Job ID for async operations")
    estimated_time_seconds: Optional[int] = Field(
        None, description="Estimated computation time"
    )
    results: Optional[
        Union[List[CentralityResult], List[CommunityResult], List[GraphPath]]
    ] = Field(None, description="Computation results")
    computation_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Computation metadata"
    )
    errors: List[str] = Field(default_factory=list, description="Any errors")
    cached: bool = Field(default=False, description="Results from cache")


class GraphAnalyticsResponse(BaseModel):
    """Response for graph analytics"""

    total_entities: int = Field(..., description="Total entities")
    total_relationships: int = Field(..., description="Total relationships")
    entity_type_distribution: Dict[EntityType, int] = Field(
        ..., description="Entity type distribution"
    )
    relationship_type_distribution: Dict[RelationshipType, int] = Field(
        ..., description="Relationship type distribution"
    )
    graph_density: float = Field(..., description="Graph density")
    average_degree: float = Field(..., description="Average node degree")
    connected_components: int = Field(..., description="Number of connected components")
    largest_component_size: int = Field(..., description="Size of largest component")
    quality_metrics: Dict[str, float] = Field(..., description="Quality metrics")
    connectivity_metrics: Dict[str, float] = Field(
        ..., description="Connectivity metrics"
    )
    computation_time_ms: int = Field(..., description="Computation time")


class GraphInsight(BaseModel):
    """AI-generated graph insight"""

    id: str = Field(..., description="Insight ID")
    type: str = Field(..., description="Insight type")
    severity: str = Field(..., description="Severity level")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Insight description")
    impact_score: float = Field(..., ge=0.0, le=1.0, description="Impact score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in insight")
    affected_entity_ids: List[str] = Field(
        default_factory=list, description="Affected entities"
    )
    affected_relationship_ids: List[str] = Field(
        default_factory=list, description="Affected relationships"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Recommended actions"
    )
    action_priority: int = Field(default=1, description="Action priority")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    generated_at: datetime = Field(..., description="Generation timestamp")


class GraphInsightsResponse(BaseModel):
    """Response for graph insights"""

    insights: List[GraphInsight] = Field(..., description="Generated insights")
    total_insights: int = Field(..., description="Total number of insights")
    categories: Dict[str, int] = Field(..., description="Insights by category")
    severity_distribution: Dict[str, int] = Field(
        ..., description="Insights by severity"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Generation timestamp"
    )


# Real-time Update Models
class GraphUpdateEvent(BaseModel):
    """Real-time graph update event"""

    event_type: str = Field(..., description="Event type")
    entity_id: Optional[str] = Field(None, description="Affected entity ID")
    relationship_id: Optional[str] = Field(None, description="Affected relationship ID")
    organization_id: str = Field(..., description="Organization ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )
    user_id: Optional[str] = Field(None, description="User who triggered event")


# User Preference Models
class UserGraphPreferences(BaseModel):
    """User graph visualization preferences"""

    user_id: str = Field(..., description="User ID")
    organization_id: str = Field(..., description="Organization ID")

    # Visualization preferences
    default_layout_algorithm: LayoutAlgorithm = Field(
        default=LayoutAlgorithm.FORCE_DIRECTED
    )
    node_color_scheme: str = Field(default="type_based")
    edge_color_scheme: str = Field(default="type_based")
    show_labels: bool = Field(default=True)
    label_threshold: int = Field(
        default=50, description="Show labels for graphs with < N nodes"
    )

    # Filter preferences
    default_entity_types: List[EntityType] = Field(default_factory=list)
    default_relationship_types: List[RelationshipType] = Field(default_factory=list)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    strength_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # Analytics preferences
    preferred_centrality_metric: GraphAlgorithmType = Field(
        default=GraphAlgorithmType.DEGREE_CENTRALITY
    )
    show_community_clusters: bool = Field(default=True)
    show_isolated_nodes: bool = Field(default=False)

    # Performance preferences
    max_nodes_for_realtime: int = Field(default=500, ge=10, le=2000)
    animation_enabled: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Performance Models
class GraphPerformanceMetrics(BaseModel):
    """Performance metrics for graph operations"""

    operation_type: str = Field(..., description="Operation type")
    entity_count: int = Field(..., description="Number of entities processed")
    relationship_count: int = Field(
        ..., description="Number of relationships processed"
    )
    computation_time_ms: int = Field(
        ..., description="Computation time in milliseconds"
    )
    memory_usage_mb: int = Field(..., description="Memory usage in MB")
    cache_hit_rate: float = Field(..., description="Cache hit rate")
    algorithm: Optional[str] = Field(None, description="Algorithm used")
    organization_id: str = Field(..., description="Organization ID")
    user_id: Optional[str] = Field(None, description="User ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Error Models
class GraphAPIError(BaseModel):
    """Graph API error model"""

    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Error details"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    organization_id: str = Field(..., description="Organization ID")
    user_id: Optional[str] = Field(None, description="User ID")


# Validation
@validator("entity_types", pre=True, always=True)
def validate_entity_types(cls, v):
    """Validate entity types"""
    if v is None:
        return []
    return [EntityType(t) if isinstance(t, str) else t for t in v]


@validator("relationship_types", pre=True, always=True)
def validate_relationship_types(cls, v):
    """Validate relationship types"""
    if v is None:
        return []
    return [RelationshipType(t) if isinstance(t, str) else t for t in v]


# Utility Models
class PaginationInfo(BaseModel):
    """Pagination information"""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=200, description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


class FilterOptions(BaseModel):
    """Filter options for graph queries"""

    entity_types: List[EntityType] = Field(default_factory=list)
    relationship_types: List[RelationshipType] = Field(default_factory=list)
    confidence_min: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_max: float = Field(default=1.0, ge=0.0, le=1.0)
    strength_min: float = Field(default=0.0, ge=0.0, le=1.0)
    strength_max: float = Field(default=1.0, ge=0.0, le=1.0)
    date_range_start: Optional[datetime] = Field(None)
    date_range_end: Optional[datetime] = Field(None)
    organization_id: str = Field(..., description="Organization ID")
    custom_filters: Dict[str, Any] = Field(default_factory=dict)
