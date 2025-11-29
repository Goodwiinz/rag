/**
 * Enhanced Graph Service - API Client for Knowledge Graph Operations
 *
 * ARCHITECTURE COMPLIANCE: Frontend ONLY consumes data from backend APIs.
 * NO graph algorithm processing in frontend - all computation delegated to backend.
 *
 * Backend Services Integration:
 * - Knowledge Graph Service (Port 8003) - Entity CRUD and relationships
 * - Graph Analytics Service (Port 8009) - All algorithm processing (centrality, communities, paths)
 * - Graph Visualization API (Port 8010) - Layout computation and rendering data
 */

import { apiClient } from './apiClient';
import {
  GraphFilters,
  EntityDetails,
  KnowledgeGraphData,
  GraphNode,
  GraphEdge,
  GraphLayout,
  GraphAnalyticsDashboard,
  WebSocketGraphUpdate,
  GraphExportOptions,
  RelatedEntity,
  Community,
  DistributionData,
  PerformanceMetrics
} from '../types/knowledge-graph';

// Enhanced API Request/Response Types
export interface GraphDataRequest {
  filters?: GraphFilters;
  layout_algorithm: 'force_directed' | 'circular' | 'hierarchical' | 'geographic';
  options: {
    dimensions: { width: number; height: number };
    include_analytics: boolean;
    max_nodes?: number;
    cache_key?: string;
  };
}

export interface EntitySearchRequest {
  query: string;
  filters?: GraphFilters;
  options: {
    limit: number;
    offset: number;
    ranking: 'semantic' | 'centrality' | 'temporal' | 'confidence';
    include_snippets: boolean;
    fuzzy_search: boolean;
  };
}

export interface AnalyticsRequest {
  filters?: GraphFilters;
  metrics: Array<'centrality' | 'community_detection' | 'pathfinding' | 'graph_statistics' | 'temporal_analysis'>;
  options: {
    include_distributions: boolean;
    top_k: number;
    percentile_thresholds: number[];
    algorithms?: {
      centrality?: Array<'degree' | 'betweenness' | 'closeness' | 'eigenvector' | 'page_rank'>;
      community_detection?: 'louvain' | 'leiden' | 'walktrap';
      pathfinding?: 'dijkstra' | 'a_star' | 'bfs';
    };
  };
}

class GraphService {
  private readonly baseUrl = process.env.REACT_APP_GRAPH_SERVICE_URL || 'http://localhost:8003';
  private readonly analyticsUrl = process.env.REACT_APP_GRAPH_ANALYTICS_URL || 'http://localhost:8009';
  private readonly visualizationUrl = process.env.REACT_APP_GRAPH_VISUALIZATION_URL || 'http://localhost:8010';

  // Service health checks
  async checkServiceHealth(): Promise<{
    graph_service: boolean;
    analytics_service: boolean;
    visualization_service: boolean;
  }> {
    const [graphHealth, analyticsHealth, visualizationHealth] = await Promise.allSettled([
      apiClient.get(`${this.baseUrl}/health`),
      apiClient.get(`${this.analyticsUrl}/health`),
      apiClient.get(`${this.visualizationUrl}/health`)
    ]);

    return {
      graph_service: graphHealth.status === 'fulfilled',
      analytics_service: analyticsHealth.status === 'fulfilled',
      visualization_service: visualizationHealth.status === 'fulfilled'
    };
  }

  /**
   * Fetch complete graph data with layout and analytics
   * BACKEND RESPONSIBILITY: Layout computation, analytics calculations
   */
  async getGraphData(request: GraphDataRequest): Promise<KnowledgeGraphData> {
    const response = await apiClient.post<KnowledgeGraphData>(
      `${this.visualizationUrl}/graph/comprehensive`,
      request
    );
    return response.data;
  }

  /**
   * Get entity details with complete relationship analysis
   * BACKEND RESPONSIBILITY: Relationship strength calculation, path analysis
   */
  async getEntityDetails(
    entityId: string,
    options: {
      include_relationships: boolean;
      include_documents: boolean;
      include_related_entities: boolean;
      max_related_entities?: number;
      relationship_strength_threshold?: number;
      include_mention_contexts?: boolean;
    } = {
      include_relationships: true,
      include_documents: true,
      include_related_entities: true,
      max_related_entities: 20,
      relationship_strength_threshold: 0.3,
      include_mention_contexts: true
    }
  ): Promise<EntityDetails> {
    const response = await apiClient.get<EntityDetails>(
      `${this.baseUrl}/entities/${entityId}`,
      { params: options }
    );
    return response.data;
  }

  /**
   * Advanced entity search with multiple ranking algorithms
   * BACKEND RESPONSIBILITY: Semantic search, ranking algorithms, fuzzy matching
   */
  async searchEntities(request: EntitySearchRequest): Promise<{
    entities: GraphNode[];
    total_count: number;
    search_time: number;
    ranking_metadata: Record<string, any>;
  }> {
    const response = await apiClient.post<{
      entities: GraphNode[];
      total_count: number;
      search_time: number;
      ranking_metadata: Record<string, any>;
    }>(
      `${this.baseUrl}/entities/search`,
      request
    );
    return response.data;
  }

  /**
   * Get comprehensive analytics dashboard data
   * BACKEND RESPONSIBILITY: All analytics calculations, distributions, metrics
   */
  async getAnalyticsDashboard(request: AnalyticsRequest): Promise<GraphAnalyticsDashboard> {
    const response = await apiClient.post<GraphAnalyticsDashboard>(
      `${this.analyticsUrl}/analytics/comprehensive`,
      request
    );
    return response.data;
  }

  /**
   * Get node neighborhood with layout
   * BACKEND RESPONSIBILITY: Neighborhood computation, layout positioning
   */
  async getNodeNeighborhood(
    nodeId: string,
    options: {
      depth: number;
      max_nodes: number;
      layout_algorithm: string;
      include_analytics: boolean;
    } = {
      depth: 1,
      max_nodes: 100,
      layout_algorithm: 'circular',
      include_analytics: true
    }
  ): Promise<KnowledgeGraphData> {
    const response = await apiClient.post<KnowledgeGraphData>(
      `${this.visualizationUrl}/neighborhood`,
      { node_id: nodeId, ...options }
    );
    return response.data;
  }

  /**
   * Find shortest path between nodes
   * BACKEND RESPONSIBILITY: Path computation algorithms
   */
  async findShortestPath(
    sourceId: string,
    targetId: string,
    algorithm: 'dijkstra' | 'a_star' | 'bfs' = 'dijkstra'
  ): Promise<{
    path: string[];
    total_weight: number;
    computation_time: number;
    alternative_paths?: Array<{
      path: string[];
      weight: number;
    }>;
  }> {
    const response = await apiClient.post<{
      path: string[];
      total_weight: number;
      computation_time: number;
      alternative_paths?: Array<{
        path: string[];
        weight: number;
      }>;
    }>(
      `${this.analyticsUrl}/pathfinding/shortest`,
      {
        source_id: sourceId,
        target_id: targetId,
        algorithm,
        weight_property: 'weight',
        include_alternatives: true
      }
    );
    return response.data;
  }

  /**
   * Get community detection results
   * BACKEND RESPONSIBILITY: Community detection algorithms
   */
  async getCommunities(
    options: {
      algorithm: 'louvain' | 'leiden' | 'walktrap';
      resolution: number;
      include_intermediate_results: boolean;
    } = {
      algorithm: 'louvain',
      resolution: 1.0,
      include_intermediate_results: false
    }
  ): Promise<{
    communities: Community[];
    modularity_score: number;
    computation_time: number;
    quality_metrics: {
      silhouette_score?: number;
      conductance?: number;
    };
  }> {
    const response = await apiClient.post<{
      communities: Community[];
      modularity_score: number;
      computation_time: number;
      quality_metrics: {
        silhouette_score?: number;
        conductance?: number;
      };
    }>(
      `${this.analyticsUrl}/communities/detect`,
      options
    );
    return response.data;
  }

  /**
   * Get related entities with computed similarity scores
   * BACKEND RESPONSIBILITY: Similarity calculation, relationship strength
   */
  async getRelatedEntities(
    entityId: string,
    options: {
      max_entities: number;
      similarity_threshold: number;
      include_path_lengths: boolean;
    } = {
      max_entities: 20,
      similarity_threshold: 0.3,
      include_path_lengths: true
    }
  ): Promise<RelatedEntity[]> {
    const response = await apiClient.post<RelatedEntity[]>(
      `${this.analyticsUrl}/entities/${entityId}/related`,
      options
    );
    return response.data;
  }

  /**
   * Export graph data in multiple formats
   * BACKEND RESPONSIBILITY: Data formatting, conversion, export preparation
   */
  async exportGraph(options: GraphExportOptions): Promise<Blob> {
    const response = await apiClient.post(
      `${this.baseUrl}/export`,
      options,
      { responseType: 'blob' }
    );
    return response.data;
  }

  /**
   * Get real-time performance metrics
   * BACKEND RESPONSIBILITY: Metrics collection, aggregation
   */
  async getPerformanceMetrics(): Promise<PerformanceMetrics> {
    const response = await apiClient.get<PerformanceMetrics>(
      `${this.analyticsUrl}/performance/metrics`
    );
    return response.data;
  }

  /**
   * Batch entity operations
   * BACKEND RESPONSIBILITY: Bulk processing, validation, transaction management
   */
  async batchProcessEntities(
    operation: 'merge' | 'split' | 'delete' | 'update',
    entityIds: string[],
    options: {
      dry_run?: boolean;
      validation_mode?: 'strict' | 'lenient';
      notification_preferences?: Record<string, any>;
    } = {}
  ): Promise<{
    success: string[];
    errors: Array<{ id: string; error: string }>;
    warnings: Array<{ id: string; warning: string }>;
    operation_id: string;
  }> {
    const response = await apiClient.post<{
      success: string[];
      errors: Array<{ id: string; error: string }>;
      warnings: Array<{ id: string; warning: string }>;
      operation_id: string;
    }>(
      `${this.baseUrl}/entities/batch`,
      {
        operation,
        entity_ids: entityIds,
        options
      }
    );
    return response.data;
  }

  /**
   * Get graph statistics summary
   * BACKEND RESPONSIBILITY: Statistical aggregation, metric calculation
   */
  async getGraphSummary(filters?: GraphFilters): Promise<{
    node_count: number;
    edge_count: number;
    entity_type_counts: Record<string, number>;
    relationship_type_counts: Record<string, number>;
    avg_node_degree: number;
    graph_density: number;
    clustering_coefficient: number;
    connected_components: number;
    largest_component_size: number;
    update_timestamp: string;
  }> {
    const response = await apiClient.post<{
      node_count: number;
      edge_count: number;
      entity_type_counts: Record<string, number>;
      relationship_type_counts: Record<string, number>;
      avg_node_degree: number;
      graph_density: number;
      clustering_coefficient: number;
      connected_components: number;
      largest_component_size: number;
      update_timestamp: string;
    }>(
      `${this.analyticsUrl}/summary`,
      { filters }
    );
    return response.data;
  }

  /**
   * Subscribe to WebSocket updates
   * BACKEND RESPONSIBILITY: Real-time data streaming, change notifications
   */
  createWebSocketSubscription(filters?: GraphFilters): WebSocket {
    const ws = apiClient.createWebSocket(`${this.visualizationUrl}/ws/subscribe`);

    // Send subscription message
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'subscribe',
        filters,
        client_timestamp: new Date().toISOString()
      }));
    } else {
      ws.addEventListener('open', () => {
        ws.send(JSON.stringify({
          type: 'subscribe',
          filters,
          client_timestamp: new Date().toISOString()
        }));
      });
    }

    return ws;
  }

  /**
   * Validate graph data integrity
   * BACKEND RESPONSIBILITY: Data validation, consistency checks
   */
  async validateGraphData(entityIds?: string[]): Promise<{
    is_valid: boolean;
    issues: Array<{
      type: 'error' | 'warning';
      entity_id?: string;
      message: string;
      severity: 'high' | 'medium' | 'low';
    }>;
    validation_time: number;
  }> {
    const response = await apiClient.post<{
      is_valid: boolean;
      issues: Array<{
        type: 'error' | 'warning';
        entity_id?: string;
        message: string;
        severity: 'high' | 'medium' | 'low';
      }>;
      validation_time: number;
    }>(
      `${this.baseUrl}/validate`,
      { entity_ids: entityIds }
    );
    return response.data;
  }
}

export const graphService = new GraphService();