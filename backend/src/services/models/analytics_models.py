"""
Graph Analytics Service Models
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CentralityAlgorithm(str, Enum):
    """Centrality algorithms supported"""

    PAGERANK = "pagerank"
    BETWEENNESS = "betweenness"
    CLOSENESS = "closeness"
    DEGREE = "degree"
    EIGENVECTOR = "eigenvector"


class PathAlgorithm(str, Enum):
    """Path finding algorithms supported"""

    DIJKSTRA = "dijkstra"
    BFS = "bfs"
    ASTAR = "astar"
    FLOYD_WARSHALL = "floyd_warshall"


class CommunityAlgorithm(str, Enum):
    """Community detection algorithms supported"""

    LOUVAIN = "louvain"
    LABEL_PROPAGATION = "label_propagation"
    WALKTRAP = "walktrap"
    INFOMAP = "infomap"


class JobType(str, Enum):
    """Background job types"""

    CENTRALITY_COMPUTATION = "centrality_computation"
    COMMUNITY_DETECTION = "community_detection"
    PATH_ANALYSIS = "path_analysis"
    GRAPH_INSIGHTS = "graph_insights"
    ANOMALY_DETECTION = "anomaly_detection"
    GROWTH_ANALYSIS = "growth_analysis"


class JobStatus(str, Enum):
    """Job status values"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InsightType(str, Enum):
    """Graph insight types"""

    KEY_ENTITIES = "key_entities"
    BRIDGE_ENTITIES = "bridge_entities"
    CLUSTERS = "clusters"
    ANOMALIES = "anomalies"
    GROWTH_TRENDS = "growth_trends"
    CONNECTIVITY_PATTERNS = "connectivity_patterns"
    TEMPORAL_PATTERNS = "temporal_patterns"


# Request Models
class CentralityRequest(BaseModel):
    """Request for centrality analysis"""

    algorithm: CentralityAlgorithm = Field(
        ..., description="Centrality algorithm to use"
    )
    entity_types: Optional[List[str]] = Field(
        None, description="Filter by entity types"
    )
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum number of results"
    )
    weight_property: Optional[str] = Field(
        None, description="Property to use as weight"
    )
    force_recompute: bool = Field(
        default=False, description="Force recomputation, ignore cache"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Algorithm-specific parameters"
    )


class CentralityResult(BaseModel):
    """Single centrality result"""

    entity_id: str = Field(..., description="Entity ID")
    entity_name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type")
    centrality_score: float = Field(..., description="Centrality score")
    rank: int = Field(..., description="Rank in results")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class CentralityResponse(BaseModel):
    """Response for centrality analysis"""

    algorithm: CentralityAlgorithm = Field(..., description="Algorithm used")
    results: List[CentralityResult] = Field(..., description="Centrality results")
    computation_time: float = Field(..., description="Time taken to compute in seconds")
    node_count: int = Field(..., description="Number of nodes analyzed")
    timestamp: datetime = Field(..., description="Analysis timestamp")


class PathRequest(BaseModel):
    """Request for path finding"""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    algorithm: PathAlgorithm = Field(
        default=PathAlgorithm.BFS, description="Path algorithm"
    )
    weight_property: Optional[str] = Field(
        "strength", description="Property to use as weight"
    )
    max_depth: int = Field(default=5, ge=1, le=10, description="Maximum path depth")
    max_paths: int = Field(
        default=10, ge=1, le=100, description="Maximum number of paths"
    )
    force_recompute: bool = Field(default=False, description="Force recomputation")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PathStep(BaseModel):
    """Single step in a path"""

    entity_id: str = Field(..., description="Entity ID")
    entity_name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type")
    relationship_id: Optional[str] = Field(
        None, description="Relationship ID to next step"
    )
    relationship_type: Optional[str] = Field(
        None, description="Relationship type to next step"
    )
    weight: Optional[float] = Field(None, description="Weight of this step")


class GraphPath(BaseModel):
    """A path through the graph"""

    path_id: str = Field(..., description="Unique path identifier")
    steps: List[PathStep] = Field(..., description="Path steps")
    total_weight: float = Field(..., description="Total path weight")
    path_length: int = Field(..., description="Number of steps in path")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PathResponse(BaseModel):
    """Response for path finding"""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    algorithm: PathAlgorithm = Field(..., description="Algorithm used")
    paths: List[GraphPath] = Field(..., description="Found paths")
    computation_time: float = Field(..., description="Computation time in seconds")
    path_count: int = Field(..., description="Number of paths found")
    timestamp: datetime = Field(..., description="Analysis timestamp")


class CommunityRequest(BaseModel):
    """Request for community detection"""

    algorithm: CommunityAlgorithm = Field(
        ..., description="Community detection algorithm"
    )
    entity_types: Optional[List[str]] = Field(
        None, description="Filter by entity types"
    )
    resolution: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Resolution parameter"
    )
    max_iterations: int = Field(
        default=100, ge=1, le=1000, description="Maximum iterations"
    )
    min_community_size: int = Field(
        default=3, ge=2, description="Minimum community size"
    )
    force_recompute: bool = Field(default=False, description="Force recomputation")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Community(BaseModel):
    """Detected community"""

    community_id: str = Field(..., description="Community identifier")
    entity_count: int = Field(..., description="Number of entities in community")
    entities: List[str] = Field(..., description="Entity IDs in community")
    modularity_contribution: float = Field(..., description="Modularity contribution")
    dominant_entity_type: str = Field(..., description="Most common entity type")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommunityResponse(BaseModel):
    """Response for community detection"""

    algorithm: CommunityAlgorithm = Field(..., description="Algorithm used")
    communities: List[Community] = Field(..., description="Detected communities")
    computation_time: float = Field(..., description="Computation time in seconds")
    community_count: int = Field(..., description="Number of communities detected")
    modularity_score: float = Field(..., description="Overall modularity score")
    timestamp: datetime = Field(..., description="Analysis timestamp")


# Background Job Models
class AnalyticsJobRequest(BaseModel):
    """Request for background analytics job"""

    job_type: JobType = Field(..., description="Type of analytics job")
    parameters: Dict[str, Any] = Field(..., description="Job parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority")
    scheduled_time: Optional[datetime] = Field(
        None, description="Scheduled execution time"
    )
    timeout_seconds: Optional[int] = Field(None, description="Custom timeout")
    retry_count: int = Field(default=3, ge=0, le=10, description="Number of retries")


class AnalyticsJobResponse(BaseModel):
    """Response for analytics job"""

    job_id: str = Field(..., description="Unique job identifier")
    job_type: JobType = Field(..., description="Job type")
    status: JobStatus = Field(..., description="Current job status")
    parameters: Dict[str, Any] = Field(..., description="Job parameters")
    tenant_id: str = Field(..., description="Tenant ID")
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Job progress")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )


# Graph Insights Models
class GraphInsightsRequest(BaseModel):
    """Request for graph insights"""

    insight_types: List[InsightType] = Field(
        ..., description="Types of insights to generate"
    )
    entity_types: Optional[List[str]] = Field(
        None, description="Filter by entity types"
    )
    time_range: Optional[Dict[str, datetime]] = Field(
        None, description="Time range for analysis"
    )
    force_recompute: bool = Field(default=False, description="Force recomputation")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class KeyEntityInsight(BaseModel):
    """Key entity insight"""

    entity_id: str = Field(..., description="Entity ID")
    entity_name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type")
    importance_score: float = Field(..., description="Importance score")
    key_metrics: Dict[str, float] = Field(..., description="Key metrics")
    reasoning: str = Field(..., description="Why this entity is important")


class BridgeEntityInsight(BaseModel):
    """Bridge entity insight"""

    entity_id: str = Field(..., description="Entity ID")
    entity_name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type")
    betweenness_score: float = Field(..., description="Betweenness score")
    connected_communities: List[str] = Field(..., description="Communities connected")
    bridge_strength: float = Field(..., description="Bridge strength")


class ClusterInsight(BaseModel):
    """Graph cluster insight"""

    cluster_id: str = Field(..., description="Cluster identifier")
    entity_count: int = Field(..., description="Number of entities")
    density: float = Field(..., description="Cluster density")
    dominant_entity_types: List[str] = Field(
        ..., description="Most common entity types"
    )
    key_entities: List[str] = Field(..., description="Key entities in cluster")
    description: str = Field(..., description="Cluster description")


class AnomalyInsight(BaseModel):
    """Graph anomaly insight"""

    anomaly_id: str = Field(..., description="Anomaly identifier")
    anomaly_type: str = Field(..., description="Type of anomaly")
    entities_involved: List[str] = Field(..., description="Entities involved")
    anomaly_score: float = Field(..., description="Anomaly score")
    description: str = Field(..., description="Anomaly description")
    severity: str = Field(..., description="Anomaly severity")


class GrowthTrendInsight(BaseModel):
    """Growth trend insight"""

    metric_name: str = Field(..., description="Metric name")
    time_period: str = Field(..., description="Time period analyzed")
    growth_rate: float = Field(..., description="Growth rate")
    trend_direction: str = Field(..., description="Trend direction")
    key_drivers: List[str] = Field(..., description="Key growth drivers")


class GraphInsightsResponse(BaseModel):
    """Response for graph insights"""

    insights: Dict[str, Any] = Field(..., description="Generated insights")
    insight_types: List[InsightType] = Field(
        ..., description="Types of insights generated"
    )
    computation_time: float = Field(..., description="Computation time in seconds")
    timestamp: datetime = Field(..., description="Analysis timestamp")


# Analytics Models
class AnalyticsMetrics(BaseModel):
    """Analytics service metrics"""

    total_jobs_processed: int = Field(default=0, description="Total jobs processed")
    active_jobs: int = Field(default=0, description="Currently active jobs")
    failed_jobs: int = Field(default=0, description="Failed jobs")
    average_computation_time: float = Field(
        default=0.0, description="Average computation time"
    )
    cache_hit_rate: float = Field(default=0.0, description="Cache hit rate")
    queue_depth: int = Field(default=0, description="Current queue depth")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    cpu_usage_percent: float = Field(default=0.0, description="CPU usage percentage")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Metrics timestamp"
    )


class AlgorithmPerformance(BaseModel):
    """Algorithm performance metrics"""

    algorithm_name: str = Field(..., description="Algorithm name")
    average_execution_time: float = Field(..., description="Average execution time")
    success_rate: float = Field(..., description="Success rate")
    average_graph_size: int = Field(..., description="Average graph size processed")
    last_execution: datetime = Field(..., description="Last execution time")
    total_executions: int = Field(default=0, description="Total executions")


class SystemStatus(BaseModel):
    """Analytics service system status"""

    status: str = Field(..., description="System status")
    neo4j_status: str = Field(..., description="Neo4j connection status")
    redis_status: str = Field(..., description="Redis connection status")
    celery_status: str = Field(..., description="Celery status")
    active_workers: int = Field(default=0, description="Active Celery workers")
    queue_status: Dict[str, int] = Field(
        default_factory=dict, description="Queue status"
    )
    uptime_seconds: float = Field(default=0.0, description="Service uptime")
    last_health_check: datetime = Field(
        default_factory=datetime.utcnow, description="Last health check"
    )
