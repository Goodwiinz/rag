"""
Graph Visualization Service Models
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class LayoutAlgorithm(str, Enum):
    """Available layout algorithms"""
    FORCE_DIRECTED = "force_directed"
    CIRCULAR = "circular"
    HIERARCHICAL = "hierarchical"
    GRID = "grid"
    RANDOM = "random"
    SPIRAL = "spiral"
    CONCENTRIC = "concentric"


class GraphSizeCategory(str, Enum):
    """Graph size categories for optimization"""
    SMALL = "small"           # < 100 nodes
    MEDIUM = "medium"         # 100-1000 nodes
    LARGE = "large"           # 1000-10000 nodes
    EXTRA_LARGE = "xlarge"    # > 10000 nodes


class NodeShape(str, Enum):
    """Node shapes"""
    CIRCLE = "circle"
    SQUARE = "square"
    TRIANGLE = "triangle"
    DIAMOND = "diamond"
    STAR = "star"
    HEXAGON = "hexagon"


class EdgeType(str, Enum):
    """Edge types for rendering"""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    THICK = "thick"


# Request Models
class FilterOptions(BaseModel):
    """Filter options for graph visualization"""
    entity_types: Optional[List[str]] = Field(None, description="Filter by entity types")
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types")
    min_degree: Optional[int] = Field(None, ge=0, description="Minimum node degree")
    max_degree: Optional[int] = Field(None, ge=0, description="Maximum node degree")
    min_strength: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum relationship strength")
    max_strength: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum relationship strength")
    date_range: Optional[Dict[str, datetime]] = Field(None, description="Filter by date range")
    custom_filters: Optional[Dict[str, Any]] = Field(None, description="Custom filter criteria")


class StyleOptions(BaseModel):
    """Styling options for graph visualization"""
    node_colors: Optional[Dict[str, str]] = Field(None, description="Color mapping for entity types")
    edge_colors: Optional[Dict[str, str]] = Field(None, description="Color mapping for relationship types")
    node_size_range: Optional[List[int]] = Field([5, 20], description="Node size range [min, max]")
    edge_width_range: Optional[List[float]] = Field([1, 5], description="Edge width range [min, max]")
    node_shapes: Optional[Dict[str, NodeShape]] = Field(None, description="Shape mapping for entity types")
    edge_types: Optional[Dict[str, EdgeType]] = Field(None, description="Type mapping for relationship types")
    opacity: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Overall opacity")
    show_labels: bool = Field(True, description="Show node labels")
    label_threshold: Optional[int] = Field(None, description="Minimum degree to show label")
    font_size: Optional[int] = Field(12, description="Label font size")


class LayoutOptions(BaseModel):
    """Layout algorithm options"""
    iterations: Optional[int] = Field(1000, ge=100, le=10000, description="Number of iterations")
    threshold: Optional[float] = Field(1e-4, ge=1e-6, le=1e-2, description="Convergence threshold")
    strength: Optional[float] = Field(1.0, ge=0.1, le=10.0, description="Layout strength")
    repulsion: Optional[float] = Field(100.0, ge=10.0, le=1000.0, description="Node repulsion force")
    gravity: Optional[float] = Field(0.1, ge=0.0, le=1.0, description="Gravity force")
    center_layout: bool = Field(True, description="Center the layout")
    fit_to_view: bool = Field(True, description="Fit layout to viewport")


class GraphVisualizationRequest(BaseModel):
    """Request for graph visualization"""
    filters: Optional[FilterOptions] = Field(None, description="Graph filters")
    layout_algorithm: LayoutAlgorithm = Field(LayoutAlgorithm.FORCE_DIRECTED, description="Layout algorithm")
    layout_options: Optional[LayoutOptions] = Field(None, description="Layout options")
    style_options: Optional[StyleOptions] = Field(None, description="Style options")
    max_nodes: Optional[int] = Field(1000, ge=1, le=50000, description="Maximum number of nodes")
    max_edges: Optional[int] = Field(2000, ge=1, le=100000, description="Maximum number of edges")
    force_recompute: bool = Field(False, description="Force recomputation, ignore cache")
    preprocessing_options: Optional[Dict[str, Any]] = Field(None, description="Data preprocessing options")


class ProgressiveLoadRequest(BaseModel):
    """Request for progressive graph loading"""
    session_id: str = Field(..., description="Unique session identifier")
    batch_number: int = Field(..., ge=1, description="Batch number to load")
    batch_size: int = Field(500, ge=100, le=2000, description="Batch size")
    filters: Optional[FilterOptions] = Field(None, description="Graph filters")
    layout_algorithm: LayoutAlgorithm = Field(LayoutAlgorithm.FORCE_DIRECTED, description="Layout algorithm")
    incremental_layout: bool = Field(True, description="Use incremental layout")


class InteractiveFilterRequest(BaseModel):
    """Request for interactive filtering"""
    base_visualization_id: str = Field(..., description="Base visualization ID")
    filters: FilterOptions = Field(..., description="Filters to apply")
    layout_algorithm: LayoutAlgorithm = Field(LayoutAlgorithm.FORCE_DIRECTED, description="Layout algorithm")
    recompute_layout: bool = Field(True, description="Recompute layout after filtering")


# Data Models
class VisualizationNode(BaseModel):
    """Node for graph visualization"""
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Node label")
    type: str = Field(..., description="Node type")
    x: Optional[float] = Field(None, description="X coordinate")
    y: Optional[float] = Field(None, description="Y coordinate")
    size: Optional[float] = Field(10.0, description="Node size")
    color: Optional[str] = Field("#4ecdc4", description="Node color")
    shape: Optional[NodeShape] = Field(NodeShape.CIRCLE, description="Node shape")
    opacity: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Node opacity")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional node properties")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Visualization metadata")
    is_central: Optional[bool] = Field(False, description="Whether this is a central node")
    degree: Optional[int] = Field(0, description="Node degree")
    cluster_id: Optional[str] = Field(None, description="Cluster identifier")


class VisualizationEdge(BaseModel):
    """Edge for graph visualization"""
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Edge type")
    weight: Optional[float] = Field(1.0, description="Edge weight")
    width: Optional[float] = Field(2.0, description="Edge width")
    color: Optional[str] = Field("#636e72", description="Edge color")
    edge_type: Optional[EdgeType] = Field(EdgeType.SOLID, description="Edge rendering type")
    opacity: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Edge opacity")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional edge properties")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Visualization metadata")
    strength: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Relationship strength")
    bidirectional: Optional[bool] = Field(False, description="Whether edge is bidirectional")


class GraphLayout(BaseModel):
    """Graph layout information"""
    algorithm: LayoutAlgorithm = Field(..., description="Layout algorithm used")
    dimensions: Dict[str, float] = Field(..., description="Layout dimensions [width, height]")
    center: Dict[str, float] = Field(..., description="Layout center coordinates")
    scale: float = Field(1.0, description="Layout scale")
    rotation: float = Field(0.0, description="Layout rotation in degrees")
    bounding_box: Dict[str, float] = Field(..., description="Bounding box [min_x, min_y, max_x, max_y]")
    convergence_info: Optional[Dict[str, Any]] = Field(None, description="Convergence information")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional layout metadata")


class GraphVisualizationResponse(BaseModel):
    """Response for graph visualization"""
    visualization_id: str = Field(..., description="Unique visualization identifier")
    nodes: List[VisualizationNode] = Field(..., description="Visualization nodes")
    edges: List[VisualizationEdge] = Field(..., description="Visualization edges")
    layout: GraphLayout = Field(..., description="Layout information")
    metadata: Dict[str, Any] = Field(..., description="Visualization metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


# Progressive Loading Models
class BatchInfo(BaseModel):
    """Information about a loaded batch"""
    batch_number: int = Field(..., description="Batch number")
    batch_size: int = Field(..., description="Number of items in batch")
    cumulative_nodes: int = Field(..., description="Total nodes loaded so far")
    cumulative_edges: int = Field(..., description="Total edges loaded so far")
    has_more: bool = Field(..., description="Whether more batches are available")
    loading_time: float = Field(..., description="Time to load this batch")


class ProgressiveVisualizationResponse(GraphVisualizationResponse):
    """Response for progressive visualization"""
    batch_info: BatchInfo = Field(..., description="Batch loading information")
    session_id: str = Field(..., description="Progressive loading session ID")


# Filter Models
class FilterResult(BaseModel):
    """Result of filtering operation"""
    original_nodes: int = Field(..., description="Original node count")
    original_edges: int = Field(..., description="Original edge count")
    filtered_nodes: int = Field(..., description="Filtered node count")
    filtered_edges: int = Field(..., description="Filtered edge count")
    filters_applied: List[str] = Field(..., description="Applied filters")
    processing_time: float = Field(..., description="Filter processing time")


# Analytics Models
class VisualizationMetrics(BaseModel):
    """Visualization performance metrics"""
    node_count: int = Field(default=0, description="Number of nodes")
    edge_count: int = Field(default=0, description="Number of edges")
    layout_time: float = Field(default=0.0, description="Layout computation time")
    rendering_time: float = Field(default=0.0, description="Rendering time")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    cache_hit_rate: float = Field(default=0.0, description="Cache hit rate")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")


class PerformanceStats(BaseModel):
    """Performance statistics"""
    total_visualizations: int = Field(default=0, description="Total visualizations created")
    active_sessions: int = Field(default=0, description="Active progressive loading sessions")
    average_layout_time: float = Field(default=0.0, description="Average layout time")
    peak_memory_usage: float = Field(default=0.0, description="Peak memory usage")
    cache_efficiency: float = Field(default=0.0, description="Cache efficiency")
    popular_layouts: Dict[str, int] = Field(default_factory=dict, description="Popular layout algorithms")
    popular_filters: Dict[str, int] = Field(default_factory=dict, description="Popular filters")


# Export Models
class ExportRequest(BaseModel):
    """Request for visualization export"""
    visualization_id: str = Field(..., description="Visualization ID to export")
    format: str = Field(..., description="Export format (json, csv, gexf)")
    include_layout: bool = Field(True, description="Include layout coordinates")
    include_style: bool = Field(True, description="Include style information")
    include_metadata: bool = Field(True, description="Include metadata")
    filename: Optional[str] = Field(None, description="Custom filename")


class ExportResponse(BaseModel):
    """Response for export request"""
    export_id: str = Field(..., description="Unique export identifier")
    download_url: str = Field(..., description="Download URL")
    file_size: int = Field(..., description="File size in bytes")
    format: str = Field(..., description="Export format")
    expires_at: datetime = Field(..., description="URL expiration time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Export timestamp")


# System Models
class SystemStatus(BaseModel):
    """Visualization service system status"""
    status: str = Field(..., description="Service status")
    neo4j_status: str = Field(..., description="Neo4j connection status")
    redis_status: str = Field(..., description="Redis connection status")
    active_visualizations: int = Field(default=0, description="Active visualizations")
    cache_size: int = Field(default=0, description="Cache size")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage")
    uptime_seconds: float = Field(default=0.0, description="Service uptime")
    last_health_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check")


class FeatureFlag(BaseModel):
    """Feature flag configuration"""
    name: str = Field(..., description="Feature name")
    enabled: bool = Field(..., description="Whether feature is enabled")
    description: str = Field(..., description="Feature description")
    rollout_percentage: Optional[float] = Field(None, description="Rollout percentage")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Enable conditions")