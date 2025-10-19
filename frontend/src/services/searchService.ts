import { apiClient } from './apiClient';
import { APIResponse } from '@/types/api';
import {
  SearchRequest,
  SearchResult,
  QueryHistory,
  QuerySuggestions,
  QueryProcessingSession,
  QueryProcessingUpdate,
  EnhancedSearchRequest,
  GraphData,
  GraphFilters,
} from '@/types/search';

export class SearchService {
  private readonly basePath = '/search';

  /**
   * Perform a search query
   */
  async search(request: SearchRequest): Promise<APIResponse<SearchResult>> {
    return apiClient.post(`${this.basePath}`, request);
  }

  /**
   * Perform enhanced search with processing configuration
   */
  async enhancedSearch(request: EnhancedSearchRequest): Promise<APIResponse<SearchResult>> {
    return apiClient.post(`${this.basePath}/enhanced`, request);
  }

  /**
   * Get query suggestions
   */
  async getQuerySuggestions(query: string, limit: number = 5): Promise<APIResponse<QuerySuggestions>> {
    return apiClient.get(`${this.basePath}/suggestions`, {
      params: { q: query, limit },
    });
  }

  /**
   * Get search history
   */
  async getSearchHistory(limit: number = 50): Promise<APIResponse<QueryHistory[]>> {
    return apiClient.get(`${this.basePath}/history`, {
      params: { limit },
    });
  }

  /**
   * Add query to history
   */
  async addToHistory(query: string, resultId: string): Promise<APIResponse<void>> {
    return apiClient.post(`${this.basePath}/history`, {
      query,
      result_id: resultId,
    });
  }

  /**
   * Clear search history
   */
  async clearSearchHistory(): Promise<APIResponse<void>> {
    return apiClient.delete(`${this.basePath}/history`);
  }

  /**
   * Get query processing session
   */
  async getQuerySession(sessionId: string): Promise<APIResponse<QueryProcessingSession>> {
    return apiClient.get(`${this.basePath}/sessions/${sessionId}`);
  }

  /**
   * Start a new query processing session
   */
  async startQuerySession(request: EnhancedSearchRequest): Promise<APIResponse<QueryProcessingSession>> {
    return apiClient.post(`${this.basePath}/sessions`, request);
  }

  /**
   * Cancel query processing session
   */
  async cancelQuerySession(sessionId: string): Promise<APIResponse<void>> {
    return apiClient.delete(`${this.basePath}/sessions/${sessionId}`);
  }

  /**
   * Get similar queries
   */
  async getSimilarQueries(query: string, limit: number = 5): Promise<APIResponse<string[]>> {
    return apiClient.get(`${this.basePath}/similar`, {
      params: { q: query, limit },
    });
  }

  /**
   * Get related searches
   */
  async getRelatedSearches(resultId: string, limit: number = 5): Promise<APIResponse<string[]>> {
    return apiClient.get(`${this.basePath}/related/${resultId}`, {
      params: { limit },
    });
  }

  /**
   * Search within specific documents
   */
  async searchInDocuments(
    query: string,
    documentIds: string[],
    filters?: SearchRequest['filters']
  ): Promise<APIResponse<SearchResult>> {
    return this.search({
      query,
      filters: {
        ...filters,
        document_ids: documentIds,
      },
    });
  }

  /**
   * Get real-time search results via WebSocket
   */
  createSearchWebSocket(sessionId: string, onMessage: (update: QueryProcessingUpdate) => void): WebSocket {
    const ws = apiClient.createWebSocket(`${this.basePath}/stream/${sessionId}`);

    ws.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data) as QueryProcessingUpdate;
        onMessage(update);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return ws;
  }

  /**
   * Get search analytics
   */
  async getSearchAnalytics(days: number = 30): Promise<APIResponse<{
    total_queries: number;
    unique_queries: number;
    average_latency_ms: number;
    popular_queries: Array<{ query: string; count: number }>;
    query_types: Record<string, number>;
    daily_stats: Array<{
      date: string;
      queries: number;
      avg_latency: number;
      satisfaction_score: number;
    }>;
  }>> {
    return apiClient.get(`${this.basePath}/analytics`, {
      params: { days },
    });
  }

  /**
   * Rate a search result
   */
  async rateResult(resultId: string, rating: number, feedback?: string): Promise<APIResponse<void>> {
    return apiClient.post(`${this.basePath}/rate`, {
      result_id: resultId,
      rating,
      feedback,
    });
  }

  /**
   * Export search results
   */
  async exportResults(
    resultIds: string[],
    format: 'json' | 'csv' | 'pdf' = 'json'
  ): Promise<Blob> {
    const response = await apiClient.client.post(
      `${this.basePath}/export`,
      {
        result_ids: resultIds,
        format,
      },
      {
        responseType: 'blob',
      }
    );

    return response.data;
  }

  /**
   * Get search performance metrics
   */
  async getPerformanceMetrics(): Promise<APIResponse<{
    average_response_time: number;
    p95_response_time: number;
    p99_response_time: number;
    cache_hit_rate: number;
    error_rate: number;
    throughput_per_second: number;
    resource_utilization: {
      cpu_percent: number;
      memory_percent: number;
      disk_io_percent: number;
    };
  }>> {
    return apiClient.get(`${this.basePath}/performance`);
  }

  /**
   * Save search as alert
   */
  async saveSearchAlert(
    query: string,
    filters?: SearchRequest['filters'],
    name?: string
  ): Promise<APIResponse<{ alert_id: string }>> {
    return apiClient.post(`${this.basePath}/alerts`, {
      query,
      filters,
      name,
    });
  }

  /**
   * Get saved search alerts
   */
  async getSearchAlerts(): Promise<APIResponse<Array<{
    id: string;
    name: string;
    query: string;
    filters?: SearchRequest['filters'];
    created_at: string;
    last_triggered?: string;
    is_active: boolean;
  }>>> {
    return apiClient.get(`${this.basePath}/alerts`);
  }

  /**
   * Delete search alert
   */
  async deleteSearchAlert(alertId: string): Promise<APIResponse<void>> {
    return apiClient.delete(`${this.basePath}/alerts/${alertId}`);
  }
}

// Create singleton instance
export const searchService = new SearchService();