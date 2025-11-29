/**
 * Graph Analytics Service - API Client for Graph Analytics
 *
 * Consumes pre-computed analytics data from backend analytics service.
 * Frontend only displays analytics, performs no computations.
 */

import { apiClient } from './apiClient';
import { GraphAnalyticsData } from './graphService';

export interface CentralityMetrics {
  nodeId: string;
  degree: number;
  betweenness: number;
  closeness: number;
  eigenvector: number;
  pageRank: number;
}

export interface CommunityAnalytics {
  communityId: string;
  nodeCount: number;
  edgeCount: number;
  density: number;
  modularity: number;
  dominantEntityType: string;
  topNodes: Array<{
    nodeId: string;
    centrality: number;
  }>;
}

export interface PathAnalytics {
  sourceId: string;
  targetId: string;
  shortestPath: string[];
  pathLength: number;
  alternativePaths: Array<{
    path: string[];
    length: number;
    weight: number;
  }>;
  pathStrength: number;
}

export interface GraphEvolutionMetrics {
  timestamp: string;
  nodeCount: number;
  edgeCount: number;
  averageDegree: number;
  clusteringCoefficient: number;
  connectedComponents: number;
  largestComponentSize: number;
}

export interface InsightData {
  type: 'anomaly' | 'trend' | 'pattern' | 'recommendation';
  title: string;
  description: string;
  confidence: number;
  impact: 'low' | 'medium' | 'high';
  actionable: boolean;
  relatedEntities: string[];
  suggestedActions: string[];
}

export interface AnalyticsDashboard {
  overview: {
    totalNodes: number;
    totalEdges: number;
    averageDegree: number;
    graphDensity: number;
    clusteringCoefficient: number;
    connectedComponents: number;
  };
  centralities: CentralityMetrics[];
  communities: CommunityAnalytics[];
  topologicalInsights: InsightData[];
  evolution: GraphEvolutionMetrics[];
  recommendations: InsightData[];
}

class AnalyticsService {
  private baseUrl = process.env.REACT_APP_GRAPH_ANALYTICS_URL || 'http://localhost:8009';

  /**
   * Get complete analytics dashboard - backend aggregates all metrics
   */
  async getAnalyticsDashboard(filters?: any): Promise<AnalyticsDashboard> {
    const response = await apiClient.post<AnalyticsDashboard>(
      `${this.baseUrl}/dashboard`,
      {
        filters,
        include_insights: true,
        include_recommendations: true,
        time_range: '30d'
      }
    );
    return response.data;
  }

  /**
   * Get centrality metrics - backend computes all centrality measures
   */
  async getCentralityMetrics(
    nodeIds?: string[],
    metrics: string[] = ['degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank']
  ): Promise<CentralityMetrics[]> {
    const response = await apiClient.post<{ metrics: CentralityMetrics[] }>(
      `${this.baseUrl}/centrality`,
      {
        node_ids: nodeIds,
        metrics,
        normalize: true,
        include_metadata: true
      }
    );
    return response.data.metrics;
  }

  /**
   * Get community analytics - backend performs community detection
   */
  async getCommunityAnalytics(
    algorithm: string = 'louvain',
    resolution: number = 1.0
  ): Promise<CommunityAnalytics[]> {
    const response = await apiClient.post<{ communities: CommunityAnalytics[] }>(
      `${this.baseUrl}/communities`,
      {
        algorithm,
        resolution,
        include_node_details: true,
        include_analytics: true
      }
    );
    return response.data.communities;
  }

  /**
   * Get path analytics - backend computes optimal paths
   */
  async getPathAnalytics(
    sourceId: string,
    targetId: string,
    algorithm: string = 'dijkstra'
  ): Promise<PathAnalytics> {
    const response = await apiClient.post<PathAnalytics>(
      `${this.baseUrl}/path-analytics`,
      {
        source_id: sourceId,
        target_id: targetId,
        algorithm,
        include_alternatives: true,
        max_alternatives: 5
      }
    );
    return response.data;
  }

  /**
   * Get graph evolution metrics - backend tracks changes over time
   */
  async getGraphEvolution(
    timeRange: string = '30d',
    granularity: string = 'daily'
  ): Promise<GraphEvolutionMetrics[]> {
    const response = await apiClient.get<{ evolution: GraphEvolutionMetrics[] }>(
      `${this.baseUrl}/evolution`,
      {
        params: {
          time_range: timeRange,
          granularity
        }
      }
    );
    return response.data.evolution;
  }

  /**
   * Get topological insights - backend generates AI-powered insights
   */
  async getTopologicalInsights(
    insightTypes: string[] = ['anomaly', 'trend', 'pattern', 'recommendation']
  ): Promise<InsightData[]> {
    const response = await apiClient.post<{ insights: InsightData[] }>(
      `${this.baseUrl}/insights`,
      {
        insight_types: insightTypes,
        confidence_threshold: 0.7,
        max_insights: 20
      }
    );
    return response.data.insights;
  }

  /**
   * Get node importance ranking - backend ranks nodes by importance
   */
  async getNodeImportanceRanking(
    limit: number = 50,
    criteria: string[] = ['centrality', 'connectivity', 'activity']
  ): Promise<Array<{
    nodeId: string;
    rank: number;
    score: number;
    criteria_scores: Record<string, number>;
  }>> {
    const response = await apiClient.post<{
      rankings: Array<{
        nodeId: string;
        rank: number;
        score: number;
        criteria_scores: Record<string, number>;
      }>;
    }>(
      `${this.baseUrl}/ranking/nodes`,
      {
        limit,
        criteria,
        weighting: 'balanced'
      }
    );
    return response.data.rankings;
  }

  /**
   * Export analytics data - backend formats analytics for export
   */
  async exportAnalyticsData(
    format: 'json' | 'csv' | 'xlsx',
    analyticsType: 'all' | 'centrality' | 'communities' | 'insights'
  ): Promise<Blob> {
    const response = await apiClient.post(
      `${this.baseUrl}/export`,
      {
        format,
        analytics_type: analyticsType,
        include_metadata: true,
        include_timestamps: true
      },
      {
        responseType: 'blob'
      }
    );
    return response.data;
  }
}

export const analyticsService = new AnalyticsService();