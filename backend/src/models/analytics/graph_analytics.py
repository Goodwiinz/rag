"""
Graph analytics models for Neo4j knowledge graph analysis
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, validator, ConfigDict
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, JSON, Integer, ForeignKey,
    Float, Enum as SQLEnum, Numeric, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..base import BaseModel as SQLBaseModel, GUID


class GraphAlgorithmType(str, Enum):
    """Types of graph algorithms"""
    PAGERANK = "pagerank"
    BETWEENNESS_CENTRALITY = "betweenness_centrality"
    CLOSENESS_CENTRALITY = "closeness_centrality"
    EIGENVECTOR_CENTRALITY = "eigenvector_centrality"
    DEGREE_CENTRALITY = "degree_centrality"
    COMMUNITY_DETECTION = "community_detection"
    CONNECTED_COMPONENTS = "connected_components"
    STRONGLY_CONNECTED = "strongly_connected"
    SHORTEST_PATH = "shortest_path"
    ALL_PATHS = "all_paths"
    TRIANGLE_COUNT = "triangle_count"
    CLUSTERING_COEFFICIENT = "clustering_coefficient"
    LABEL_PROPAGATION = "label_propagation"
    LOUVAIN = "louvain"
    INFOMAP = "infomap"


class NodeType(str, Enum):
    """Types of graph nodes"""
    ENTITY = "entity"
    DOCUMENT = "document"
    CONCEPT = "concept"
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    TOPIC = "topic"
    KEYWORD = "keyword"
    CUSTOM = "custom"


class EdgeType(str, Enum):
    """Types of graph edges"""
    MENTIONS = "mentions"
    CONTAINS = "contains"
    RELATED_TO = "related_to"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    REFERENCES = "references"
    CITES = "cites"
    WORKS_WITH = "works_with"
    LOCATED_IN = "located_in"
    OCCURRED_AT = "occurred_at"
    CUSTOM = "custom"


class GraphAnalyticsResult(SQLBaseModel):
    """Graph analytics result model"""

    __tablename__ = "graph_analytics_results"

    # Analysis identification
    analysis_type = Column(SQLEnum(GraphAlgorithmType), nullable=False, index=True)
    analysis_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Query configuration
    query_config = Column(JSON, nullable=False)  # Query parameters and filters
    graph_config = Column(JSON, nullable=True)  # Graph configuration

    # Results metadata
    node_count = Column(BigInteger, nullable=False)
    edge_count = Column(BigInteger, nullable=False)
    component_count = Column(Integer, nullable=True)
    density = Column(Float, nullable=True)

    # Execution metadata
    execution_time_ms = Column(BigInteger, nullable=False)
    memory_usage_mb = Column(Float, nullable=True)
    status = Column(String(50), default="completed", nullable=False)  # running, completed, failed
    error_message = Column(Text, nullable=True)

    # Results data
    results = Column(JSON, nullable=False)  # Algorithm-specific results
    result_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata' to avoid SQLAlchemy conflict

    # Relationships
    node_metrics = relationship("NodeMetrics", back_populates="analytics_result", cascade="all, delete-orphan")
    edge_metrics = relationship("EdgeMetrics", back_populates="analytics_result", cascade="all, delete-orphan")
    community_metrics = relationship("CommunityMetrics", back_populates="analytics_result", cascade="all, delete-orphan")


class NodeMetrics(SQLBaseModel):
    """Node-level metrics from graph analysis"""

    __tablename__ = "graph_node_metrics"

    # Foreign keys
    analytics_result_id = Column(GUID(), ForeignKey("graph_analytics_results.id"), nullable=False, index=True)

    # Node identification
    node_id = Column(String(255), nullable=False, index=True)  # Neo4j node ID
    node_type = Column(SQLEnum(NodeType), nullable=False, index=True)
    node_label = Column(String(255), nullable=True, index=True)

    # Centrality metrics
    pagerank_score = Column(Float, nullable=True)
    betweenness_centrality = Column(Float, nullable=True)
    closeness_centrality = Column(Float, nullable=True)
    eigenvector_centrality = Column(Float, nullable=True)
    degree_centrality = Column(Float, nullable=True)

    # Structural metrics
    degree = Column(Integer, nullable=False)
    in_degree = Column(Integer, nullable=True)
    out_degree = Column(Integer, nullable=True)
    clustering_coefficient = Column(Float, nullable=True)

    # Community metrics
    community_id = Column(String(255), nullable=True, index=True)
    community_size = Column(Integer, nullable=True)
    modularity = Column(Float, nullable=True)

    # Custom metrics
    custom_metrics = Column(JSON, nullable=True)

    # Relationships
    analytics_result = relationship("GraphAnalyticsResult", back_populates="node_metrics")


class EdgeMetrics(SQLBaseModel):
    """Edge-level metrics from graph analysis"""

    __tablename__ = "graph_edge_metrics"

    # Foreign keys
    analytics_result_id = Column(GUID(), ForeignKey("graph_analytics_results.id"), nullable=False, index=True)

    # Edge identification
    edge_id = Column(String(255), nullable=False, index=True)  # Neo4j relationship ID
    source_node_id = Column(String(255), nullable=False, index=True)
    target_node_id = Column(String(255), nullable=False, index=True)
    edge_type = Column(SQLEnum(EdgeType), nullable=False, index=True)

    # Edge metrics
    weight = Column(Float, nullable=True)
    betweenness = Column(Float, nullable=True)
    edge_betweenness = Column(Float, nullable=True)
    jaccard_similarity = Column(Float, nullable=True)
    adamic_adar = Column(Float, nullable=True)

    # Path metrics
    shortest_path_length = Column(Integer, nullable=True)
    bridges_count = Column(Integer, nullable=True)

    # Custom metrics
    custom_metrics = Column(JSON, nullable=True)

    # Relationships
    analytics_result = relationship("GraphAnalyticsResult", back_populates="edge_metrics")


class CommunityMetrics(SQLBaseModel):
    """Community-level metrics from graph analysis"""

    __tablename__ = "graph_community_metrics"

    # Foreign keys
    analytics_result_id = Column(GUID(), ForeignKey("graph_analytics_results.id"), nullable=False, index=True)

    # Community identification
    community_id = Column(String(255), nullable=False, index=True)
    community_label = Column(String(255), nullable=True)

    # Size metrics
    node_count = Column(Integer, nullable=False)
    edge_count = Column(Integer, nullable=False)
    density = Column(Float, nullable=True)

    # Quality metrics
    modularity = Column(Float, nullable=True)
    conductance = Column(Float, nullable=True)
    cluster_coefficient = Column(Float, nullable=True)
    silhouette_score = Column(Float, nullable=True)

    # Connectivity metrics
    internal_edges = Column(Integer, nullable=False)
    external_edges = Column(Integer, nullable=False)
    expansion = Column(Float, nullable=True)

    # Node type distribution
    node_type_distribution = Column(JSON, nullable=True)
    edge_type_distribution = Column(JSON, nullable=True)

    # Key nodes
    central_nodes = Column(JSON, nullable=True)  # Most central nodes
    bridge_nodes = Column(JSON, nullable=True)   # Nodes connecting communities

    # Relationships
    analytics_result = relationship("GraphAnalyticsResult", back_populates="community_metrics")


class PathAnalytics(SQLBaseModel):
    """Path analysis results"""

    __tablename__ = "graph_path_analytics"

    # Analysis identification
    analysis_type = Column(String(50), nullable=False, index=True)  # shortest, all, k_shortest
    source_node_id = Column(String(255), nullable=False, index=True)
    target_node_id = Column(String(255), nullable=False, index=True)

    # Path configuration
    max_depth = Column(Integer, nullable=True)
    path_count_limit = Column(Integer, nullable=True)
    weight_property = Column(String(255), nullable=True)

    # Results metadata
    total_paths_found = Column(Integer, nullable=False)
    average_path_length = Column(Float, nullable=True)
    shortest_path_length = Column(Integer, nullable=True)
    longest_path_length = Column(Integer, nullable=True)

    # Path data
    paths = Column(JSON, nullable=False)  # List of paths with nodes and edges
    path_metrics = Column(JSON, nullable=True)  # Path-specific metrics

    # Execution metadata
    execution_time_ms = Column(BigInteger, nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    error_message = Column(Text, nullable=True)


# Pydantic models for API serialization

class GraphMetrics(BaseModel):
    """Overall graph metrics"""
    node_count: int
    edge_count: int
    density: Optional[float] = None
    component_count: Optional[int] = None
    average_degree: Optional[float] = None
    average_path_length: Optional[float] = None
    clustering_coefficient: Optional[float] = None
    modularity: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class NodeMetricData(BaseModel):
    """Node metric data"""
    node_id: str
    node_type: NodeType
    node_label: Optional[str] = None
    pagerank_score: Optional[float] = None
    betweenness_centrality: Optional[float] = None
    closeness_centrality: Optional[float] = None
    eigenvector_centrality: Optional[float] = None
    degree_centrality: Optional[float] = None
    degree: int
    in_degree: Optional[int] = None
    out_degree: Optional[int] = None
    clustering_coefficient: Optional[float] = None
    community_id: Optional[str] = None
    community_size: Optional[int] = None
    modularity: Optional[float] = None
    custom_metrics: Optional[Dict[str, float]] = None

    model_config = ConfigDict(from_attributes=True)


class EdgeMetricData(BaseModel):
    """Edge metric data"""
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    weight: Optional[float] = None
    betweenness: Optional[float] = None
    edge_betweenness: Optional[float] = None
    jaccard_similarity: Optional[float] = None
    adamic_adar: Optional[float] = None
    shortest_path_length: Optional[int] = None
    bridges_count: Optional[int] = None
    custom_metrics: Optional[Dict[str, float]] = None

    model_config = ConfigDict(from_attributes=True)


class CommunityMetricData(BaseModel):
    """Community metric data"""
    community_id: str
    community_label: Optional[str] = None
    node_count: int
    edge_count: int
    density: Optional[float] = None
    modularity: Optional[float] = None
    conductance: Optional[float] = None
    cluster_coefficient: Optional[float] = None
    silhouette_score: Optional[float] = None
    internal_edges: int
    external_edges: int
    expansion: Optional[float] = None
    node_type_distribution: Optional[Dict[str, int]] = None
    edge_type_distribution: Optional[Dict[str, int]] = None
    central_nodes: Optional[List[str]] = None
    bridge_nodes: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class PathData(BaseModel):
    """Path data"""
    path_id: str
    nodes: List[str]
    edges: List[str]
    length: int
    weight: Optional[float] = None
    metrics: Optional[Dict[str, float]] = None

    model_config = ConfigDict(from_attributes=True)


class GraphAnalysisRequest(BaseModel):
    """Graph analysis request"""
    algorithm: GraphAlgorithmType
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    node_filters: Optional[Dict[str, Any]] = None
    edge_filters: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    include_node_metrics: bool = True
    include_edge_metrics: bool = True
    include_community_metrics: bool = True
    max_results: Optional[int] = Field(None, ge=1, le=100000)

    model_config = ConfigDict(from_attributes=True)


class PathAnalysisRequest(BaseModel):
    """Path analysis request"""
    analysis_type: str = Field(..., pattern="^(shortest|all|k_shortest)$")
    source_node_id: str
    target_node_id: str
    max_depth: Optional[int] = Field(None, ge=1, le=10)
    path_count_limit: Optional[int] = Field(None, ge=1, le=1000)
    weight_property: Optional[str] = None
    directed: bool = False

    model_config = ConfigDict(from_attributes=True)


class GraphAnalysisResponse(BaseModel):
    """Graph analysis response"""
    id: uuid.UUID
    analysis_type: GraphAlgorithmType
    analysis_name: str
    description: Optional[str]
    query_config: Dict[str, Any]
    graph_metrics: GraphMetrics
    node_metrics: Optional[List[NodeMetricData]] = None
    edge_metrics: Optional[List[EdgeMetricData]] = None
    community_metrics: Optional[List[CommunityMetricData]] = None
    execution_time_ms: int
    memory_usage_mb: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PathAnalysisResponse(BaseModel):
    """Path analysis response"""
    id: uuid.UUID
    analysis_type: str
    source_node_id: str
    target_node_id: str
    total_paths_found: int
    average_path_length: Optional[float] = None
    shortest_path_length: Optional[int] = None
    longest_path_length: Optional[int] = None
    paths: List[PathData]
    path_metrics: Optional[Dict[str, Any]] = None
    execution_time_ms: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GraphStatistics(BaseModel):
    """Graph statistics overview"""
    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]
    edge_types: Dict[str, int]
    density: Optional[float] = None
    connected_components: Optional[int] = None
    largest_component_size: Optional[int] = None
    average_degree: Optional[float] = None
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


class CentralityRanking(BaseModel):
    """Centrality ranking of nodes"""
    node_id: str
    node_label: Optional[str] = None
    node_type: NodeType
    score: float
    rank: int
    percentile: float

    model_config = ConfigDict(from_attributes=True)


class CentralityAnalysis(BaseModel):
    """Centrality analysis results"""
    algorithm: str
    rankings: List[CentralityRanking]
    top_nodes: List[str]
    statistics: Dict[str, float]
    distribution: Dict[str, int]  # Score distribution buckets

    model_config = ConfigDict(from_attributes=True)