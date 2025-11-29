/**
 * Graph API Types - Complete TypeScript interfaces for all backend API contracts
 *
 * These interfaces define the contract between frontend and backend graph services.
 * Frontend only consumes these types, no processing logic is included.
 */

// ============================================================================
// Core Graph Data Types
// ============================================================================

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  confidence: number;
  metadata: Record<string, any>;
  position?: {
    x: number;
    y: number;
  };
  style?: {
    color: string;
    size: number;
    shape: string;
    border_color?: string;
    border_width?: number;
    opacity?: number;
  };
  created_at: string;
  updated_at: string;
  document_ids: string[];
  entity_count: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  confidence: number;
  metadata: Record<string, any>;
  style?: {
    color: string;
    width: number;
    dash: boolean;
    opacity?: number;
    arrow_size?: number;
  };
  created_at: string;
  updated_at: string;
  document_ids: string[];
}

export interface GraphLayoutData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout: {
    algorithm: string;
    dimensions: {
      width: number;
      height: number;
    };
    bounds: {
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
    };
    parameters: Record<string, any>;
  };
  metadata: {
    total_nodes: number;
    total_edges: number;
    rendering_time_ms: number;
    layout_algorithm: string;
    generated_at: string;
  };
}

// ============================================================================
// Analytics Types
// ============================================================================

export interface CentralityMetrics {
  nodeId: string;
  degree: number;
  normalized_degree: number;
  betweenness: number;
  normalized_betweenness: number;
  closeness: number;
  normalized_closeness: number;
  eigenvector: number;
  normalized_eigenvector: number;
  pageRank: number;
  katz: number;
}

export interface CommunityAnalytics {
  communityId: string;
  nodeCount: number;
  edgeCount: number;
  density: number;
  modularity: number;
  dominantEntityType: string;
  averageConfidence: number;
  topNodes: Array<{
    nodeId: string;
    centrality: number;
    role: 'hub' | 'bridge' | 'peripheral';
  }>;
  topRelationships: Array<{
    edgeId: string;
    weight: number;
    frequency: number;
  }>;
  metadata: {
    color: string;
    label: string;
    description: string;
  };
}

export interface PathAnalytics {
  sourceId: string;
  targetId: string;
  shortestPath: string[];
  pathLength: number;
  totalWeight: number;
  alternativePaths: Array<{
    path: string[];
    length: number;
    weight: number;
    efficiency: number;
  }>;
  pathStrength: number;
  bottleneckNodes: string[];
  criticalEdges: string[];
}

export interface GraphStatistics {
  total_nodes: number;
  total_edges: number;
  average_degree: number;
  density: number;
  clustering_coefficient: number;
  connected_components: number;
  largest_component_size: number;
  average_path_length: number;
  diameter: number;
  assortativity: number;
  transitivity: number;
}

export interface GraphAnalyticsData {
  centralities: CentralityMetrics[];
  communities: CommunityAnalytics[];
  pathfinding: {
    shortest_paths: Record<string, string[]>;
    all_pairs: Record<string, Record<string, string[]>>;
  };
  statistics: GraphStatistics;
  timestamp: string;
  computation_time_ms: number;
}

// ============================================================================
// Entity Types
// ============================================================================

export interface EntityDetails {
  entity: GraphNode;
  relationships: GraphEdge[];
  documents: Array<{
    id: string;
    title: string;
    snippet: string;
    page_number?: number;
    confidence: number;
    relevance_score: number;
  }>;
  related_entities: Array<{
    entity: GraphNode;
    relationship: GraphEdge;
    strength: number;
    similarity_score: number;
  }>;
  mention_contexts: Array<{
    document_id: string;
    snippet: string;
    page_number?: number;
    confidence: number;
    context_before: string;
    context_after: string;
    position: {
      start: number;
      end: number;
    };
  }>;
  timeline: Array<{
    timestamp: string;
    type: 'created' | 'updated' | 'relationship_added' | 'relationship_removed';
    description: string;
    metadata?: Record<string, any>;
  }>;
}

export interface EntityComparison {
  entity1: GraphNode;
  entity2: GraphNode;
  similarities: {
    jaccard: number;
    cosine: number;
    euclidean: number;
    shared_neighbors: string[];
    shared_documents: string[];
    shared_types: string[];
  };
  differences: {
    unique_properties1: Record<string, any>;
    unique_properties2: Record<string, any>;
    unique_neighbors1: string[];
    unique_neighbors2: string[];
    unique_documents1: string[];
    unique_documents2: string[];
  };
  relationship_path: string[];
  path_strength: number;
  comparison_score: number;
}

// ============================================================================
// Filter and Search Types
// ============================================================================

export interface GraphFilters {
  entity_types?: string[];
  relationship_types?: string[];
  min_confidence?: number;
  max_confidence?: number;
  min_weight?: number;
  max_weight?: number;
  date_range?: {
    start: string;
    end: string;
  };
  document_ids?: string[];
  search_query?: string;
  include_metadata?: boolean;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface SearchRequest {
  query: string;
  filters?: GraphFilters;
  search_type?: 'semantic' | 'keyword' | 'hybrid';
  ranking?: 'relevance' | 'confidence' | 'recency';
  limit?: number;
  offset?: number;
  include_context?: boolean;
}

export interface SearchResult {
  entity: GraphNode;
  relevance_score: number;
  confidence: number;
  match_context: string;
  match_type: 'exact' | 'partial' | 'semantic';
  related_entities: Array<{
    entity: GraphNode;
    relationship: GraphEdge;
    score: number;
  }>;
}

// ============================================================================
// WebSocket Types
// ============================================================================

export interface WebSocketGraphUpdate {
  type: 'node_added' | 'node_removed' | 'node_updated' |
        'edge_added' | 'edge_removed' | 'edge_updated' |
        'layout_updated' | 'analytics_updated' | 'batch_operation';
  timestamp: string;
  data: {
    node?: GraphNode;
    edge?: GraphEdge;
    nodeId?: string;
    edgeId?: string;
    layout?: GraphLayoutData;
    analytics?: Partial<GraphAnalyticsData>;
    batch_operation?: {
      type: 'merge' | 'split' | 'delete' | 'update';
      affected_ids: string[];
      result: 'success' | 'partial' | 'failed';
    };
  };
  metadata?: {
    source: string;
    user_id?: string;
    session_id?: string;
    correlation_id?: string;
  };
}

// ============================================================================
// Dashboard and UI Types
// ============================================================================

export interface GraphDashboard {
  overview: {
    total_nodes: number;
    total_edges: number;
    average_degree: number;
    graph_density: number;
    clustering_coefficient: number;
    connected_components: number;
    largest_component_size: number;
  };
  entity_type_distribution: Array<{
    type: string;
    count: number;
    percentage: number;
    avg_confidence: number;
  }>;
  relationship_type_distribution: Array<{
    type: string;
    count: number;
    percentage: number;
    avg_weight: number;
  }>;
  temporal_trends: Array<{
    date: string;
    nodes_added: number;
    edges_added: number;
    entities_updated: number;
  }>;
  top_entities: Array<{
    entity: GraphNode;
    centrality_score: number;
    relationship_count: number;
  }>;
  recent_activity: Array<{
    timestamp: string;
    type: string;
    description: string;
    entity_id?: string;
    edge_id?: string;
  }>;
}

export interface VisualizationConfig {
  layout_algorithm: 'force_directed' | 'circular' | 'hierarchical' | 'grid';
  physics_enabled: boolean;
  clustering_enabled: boolean;
  node_size_property: 'degree' | 'centrality' | 'confidence' | 'fixed';
  edge_width_property: 'weight' | 'confidence' | 'fixed';
  color_scheme: 'type' | 'community' | 'confidence' | 'custom';
  show_labels: boolean;
  label_threshold: number;
  min_node_size: number;
  max_node_size: number;
  min_edge_width: number;
  max_edge_width: number;
  animation_enabled: boolean;
  zoom_limits: {
    min: number;
    max: number;
  };
}

// ============================================================================
// Export and Import Types
// ============================================================================

export interface ExportRequest {
  format: 'json' | 'graphml' | 'gexf' | 'csv' | 'png' | 'svg';
  filters?: GraphFilters;
  include_metadata?: boolean;
  include_layout?: boolean;
  include_analytics?: boolean;
  compression?: boolean;
}

export interface ImportRequest {
  format: 'json' | 'graphml' | 'gexf' | 'csv';
  merge_strategy: 'replace' | 'merge' | 'update';
  validate_data?: boolean;
  create_missing_entities?: boolean;
  update_existing_entities?: boolean;
}

export interface ImportResult {
  success: boolean;
  nodes_imported: number;
  edges_imported: number;
  nodes_updated: number;
  edges_updated: number;
  errors: Array<{
    line?: number;
    type: string;
    message: string;
    data?: any;
  }>;
  warnings: Array<{
    type: string;
    message: string;
    count: number;
  }>;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  metadata?: {
    timestamp: string;
    request_id: string;
    processing_time_ms: number;
    pagination?: {
      page: number;
      page_size: number;
      total_items: number;
      total_pages: number;
    };
  };
}

export interface PaginatedResponse<T> extends APIResponse<T[]> {
  metadata: {
    timestamp: string;
    request_id: string;
    processing_time_ms: number;
    pagination: {
      page: number;
      page_size: number;
      total_items: number;
      total_pages: number;
      has_next: boolean;
      has_previous: boolean;
    };
  };
}

// ============================================================================
// Error Types
// ============================================================================

export interface GraphAPIError {
  code: string;
  message: string;
  type: 'validation' | 'not_found' | 'permission' | 'rate_limit' | 'server' | 'network';
  details?: {
    field?: string;
    value?: any;
    constraint?: string;
    retry_after?: number;
  };
  timestamp: string;
  request_id?: string;
}

// ============================================================================
// Configuration Types
// ============================================================================

export interface GraphServiceConfig {
  endpoints: {
    knowledge_graph: string;
    analytics: string;
    visualization: string;
    websocket: string;
  };
  timeouts: {
    connect: number;
    request: number;
    upload: number;
    analytics: number;
  };
  retry: {
    max_attempts: number;
    base_delay: number;
    max_delay: number;
  };
  caching: {
    enabled: boolean;
    ttl: number;
    max_size: number;
  };
}