// Enhanced Knowledge Graph Types for Frontend-Only Architecture
// Frontend consumes data from backend APIs - no algorithm processing

export interface KnowledgeGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout: GraphLayout;
  metadata: GraphMetadata;
  filters: GraphFilters;
}

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  confidence: number;
  metadata: NodeMetadata;
  position?: GraphPosition;
  style?: NodeStyle;
  analytics?: NodeAnalytics; // Computed by backend
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: RelationshipType;
  weight: number;
  confidence: number;
  metadata: EdgeMetadata;
  style?: EdgeStyle;
  analytics?: EdgeAnalytics; // Computed by backend
}

export interface GraphLayout {
  algorithm: 'force_directed' | 'circular' | 'hierarchical' | 'geographic';
  dimensions: {
    width: number;
    height: number;
  };
  bounds: GraphBounds;
  options: LayoutOptions;
}

export interface GraphPosition {
  x: number;
  y: number;
  z?: number; // For 3D layouts
}

export interface GraphBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  minZ?: number;
  maxZ?: number;
}

export interface NodeMetadata {
  document_ids: string[];
  entity_source: string;
  extraction_method: string;
  created_at: string;
  updated_at: string;
  properties: Record<string, any>;
  tags: string[];
}

export interface EdgeMetadata {
  document_id: string;
  extraction_confidence: number;
  created_at: string;
  properties: Record<string, any>;
  temporal_data?: {
    start_time?: string;
    end_time?: string;
  };
}

export interface NodeStyle {
  color: string;
  size: number;
  shape: 'circle' | 'square' | 'triangle' | 'diamond';
  opacity: number;
  border_color?: string;
  border_width?: number;
  font?: {
    size: number;
    color: string;
    weight: 'normal' | 'bold';
  };
}

export interface EdgeStyle {
  color: string;
  width: number;
  dash?: boolean;
  opacity: number;
  arrow?: {
    to?: boolean;
    from?: boolean;
    size: number;
  };
}

export interface NodeAnalytics {
  // Computed by backend analytics service
  centrality_scores: {
    degree: number;
    betweenness: number;
    closeness: number;
    eigenvector: number;
  };
  community_id?: string;
  community_strength?: number;
  page_rank?: number;
  clustering_coefficient?: number;
}

export interface EdgeAnalytics {
  // Computed by backend analytics service
  betweenness_contribution?: number;
  bridge_strength?: number;
  structural_holes?: number;
}

export interface GraphMetadata {
  total_nodes: number;
  total_edges: number;
  graph_density: number;
  average_degree: number;
  clustering_coefficient: number;
  last_updated: string;
  version: string;
}

export interface GraphFilters {
  entity_types: EntityType[];
  relationship_types: RelationshipType[];
  min_confidence: number;
  max_confidence?: number;
  date_range?: {
    start: string;
    end: string;
  };
  document_ids?: string[];
  analytics_filters?: {
    min_centrality?: {
      degree?: number;
      betweenness?: number;
      closeness?: number;
    };
    community_ids?: string[];
    min_page_rank?: number;
  };
  layout_filters?: {
    bounding_box?: GraphBounds;
    zoom_level?: number;
  };
}

export interface GraphNodeInteraction {
  node_id: string;
  action: 'click' | 'hover' | 'select' | 'deselect' | 'context_menu';
  timestamp: string;
  related_nodes: string[];
  context: {
    query_id?: string;
    search_context?: string;
    interaction_sequence?: number;
  };
  user_action: {
    ctrl_key?: boolean;
    shift_key?: boolean;
    meta_key?: boolean;
  };
}

export interface EntityDetails {
  entity: GraphNode;
  relationships: GraphEdge[];
  documents: import('./document').Document[];
  related_entities: RelatedEntity[];
  mention_contexts: MentionContext[];
  analytics_summary: {
    total_connections: number;
    relationship_types: Record<string, number>;
    document_frequency: number;
    temporal_distribution: Array<{
      period: string;
      count: number;
    }>;
  };
}

export interface RelatedEntity {
  entity: GraphNode;
  relationship: GraphEdge;
  strength: number; // Computed by backend
  path_length?: number; // Computed by backend
  similarity_score?: number; // Computed by backend
}

export interface MentionContext {
  document_id: string;
  document_title: string;
  snippet: string;
  page_number?: number;
  section_name?: string;
  confidence: number;
  position: {
    start_char: number;
    end_char: number;
  };
  surrounding_text?: string;
}

// WebSocket and Real-time Types
export interface WebSocketGraphUpdate {
  type: 'node_added' | 'node_removed' | 'node_updated' |
        'edge_added' | 'edge_removed' | 'edge_updated' |
        'layout_updated' | 'analytics_updated' | 'batch_updated';
  timestamp: string;
  session_id: string;
  data: {
    node?: GraphNode;
    edge?: GraphEdge;
    nodeId?: string;
    edgeId?: string;
    layout?: KnowledgeGraphData; // Changed from GraphLayout to KnowledgeGraphData
    analytics?: GraphAnalyticsDashboard; // Changed from inline type
    batch_updates?: {
      nodes?: GraphNode[];
      edges?: GraphEdge[];
    };
  };
  user_context?: {
    user_id: string;
    session_id: string;
    filters?: GraphFilters;
  };
}

// Analytics Dashboard Types
export interface GraphAnalyticsDashboard {
  overview: GraphOverviewMetrics;
  centrality_analysis: CentralityAnalysis;
  community_analysis: CommunityAnalysis;
  path_analysis: PathAnalysis;
  temporal_analysis: TemporalAnalysis;
  performance_metrics: PerformanceMetrics;
}

export interface GraphOverviewMetrics {
  total_nodes: number;
  total_edges: number;
  graph_density: number;
  average_degree: number;
  clustering_coefficient: number;
  connected_components: number;
  largest_component_size: number;
  diameter: number;
  average_path_length: number;
}

export interface CentralityAnalysis {
  top_nodes: {
    degree: Array<{ node_id: string; score: number; rank: number }>;
    betweenness: Array<{ node_id: string; score: number; rank: number }>;
    closeness: Array<{ node_id: string; score: number; rank: number }>;
    eigenvector: Array<{ node_id: string; score: number; rank: number }>;
    page_rank: Array<{ node_id: string; score: number; rank: number }>;
  };
  distributions: {
    degree: DistributionData;
    betweenness: DistributionData;
    closeness: DistributionData;
  };
}

export interface CommunityAnalysis {
  communities: Community[];
  modularity_score: number;
  community_sizes: DistributionData;
  inter_community_edges: number;
  intra_community_edges: number;
}

export interface Community {
  id: string;
  nodes: string[];
  size: number;
  modularity_contribution: number;
  dominant_entity_types: EntityType[];
  key_entities: string[]; // High centrality nodes in community
  temporal_evolution?: Array<{
    timestamp: string;
    size: number;
    stability_score: number;
  }>;
}

export interface PathAnalysis {
  shortest_paths: {
    average_length: number;
    distribution: DistributionData;
    longest_paths: Array<{
      source: string;
      target: string;
      length: number;
      path: string[];
    }>;
  };
  connectivity: {
    strongly_connected_components: number;
    weakly_connected_components: number;
    bridges: string[]; // Edge IDs
    articulation_points: string[]; // Node IDs
  };
}

export interface TemporalAnalysis {
  growth_timeline: Array<{
    timestamp: string;
    nodes_added: number;
    edges_added: number;
    total_nodes: number;
    total_edges: number;
  }>;
  entity_evolution: Array<{
    entity_id: string;
    timeline: Array<{
      timestamp: string;
      event: 'created' | 'updated' | 'relationship_added' | 'relationship_removed';
      details: string;
    }>;
  }>;
}

export interface DistributionData {
  min: number;
  max: number;
  mean: number;
  median: number;
  std_dev: number;
  histogram: Array<{ bin: string; count: number }>;
  percentiles: {
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    p95: number;
    p99: number;
  };
}

export interface PerformanceMetrics {
  query_times: {
    graph_data: number;
    analytics: number;
    layout: number;
    search: number;
  };
  memory_usage: {
    graph_data: number;
    layout_data: number;
    analytics_cache: number;
  };
  cache_performance: {
    hit_rate: number;
    miss_rate: number;
    eviction_rate: number;
  };
  websocket_metrics: {
    connected_clients: number;
    messages_per_second: number;
    average_message_size: number;
  };
}

// Visualization State Types
export interface GraphVisualizationState {
  viewport: {
    zoom: number;
    pan: { x: number; y: number };
    bounds: GraphBounds;
  };
  selection: {
    nodes: Set<string>;
    edges: Set<string>;
    highlighted_nodes?: Set<string>;
    highlighted_edges?: Set<string>;
  };
  rendering: {
    nodes_visible: number;
    edges_visible: number;
    fps: number;
    render_time: number;
  };
  ui: {
    show_labels: boolean;
    show_analytics_overlay: boolean;
    color_scheme: 'default' | 'community' | 'centrality' | 'entity_type';
    layout_algorithm: string;
    clustering_enabled: boolean;
  };
}

// Export Types
export interface GraphExportOptions {
  format: 'json' | 'graphml' | 'gexf' | 'csv' | 'png' | 'svg';
  include_metadata: boolean;
  include_layout: boolean;
  include_analytics: boolean;
  filters?: GraphFilters;
  styling?: {
    node_colors: boolean;
    edge_widths: boolean;
    label_positions: boolean;
  };
}

// Re-export commonly used types with simpler names
export type EntityType = import('./search').Entity['type'];
export type RelationshipType = import('./search').Relationship['relationship_type'];

// Layout algorithm options
export interface LayoutOptions {
  physics?: {
    enabled: boolean;
    solver: 'force' | 'hierarchical' | 'barnesHut';
    repulsion_strength: number;
    attraction_strength: number;
    central_gravity: number;
    spring_length: number;
    damping: number;
  };
  clustering?: {
    enabled: boolean;
    algorithm: 'louvain' | 'leiden' | 'walktrap';
    cluster_edge_strength: number;
  };
  hierarchical?: {
    direction: 'UD' | 'DU' | 'LR' | 'RL';
    level_separation: number;
    node_spacing: number;
  };
  geographic?: {
    enabled: boolean;
    map_projection: string;
    coordinate_property: string;
  };
}

