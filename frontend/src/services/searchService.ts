import { apiClient } from './apiClient';
import { APIResponse } from '@/types/api';
import {
  SearchRequest,
  SearchResult,
  SourceReference,
  QueryHistory,
  QuerySuggestions,
  QueryProcessingSession,
  QueryProcessingUpdate,
  EnhancedSearchRequest,
  GraphData,
  GraphFilters,
} from '@/types/search';

type BackendSearchResponse = {
  search_id?: string;
  query?: string;
  results?: Array<{
    document_id: string;
    title: string;
    content_preview?: string;
    relevance_score?: number;
    document_type?: string;
  }>;
  search_time_ms?: number;
  total_results?: number;
  confidence?: number;
  coverage?: number;
  decision_trace_id?: string;
  deterministic_status?:
    | 'SUPPORTED'
    | 'INSUFFICIENT_EVIDENCE'
    | 'CONFLICTING_EVIDENCE'
    | 'NO_MATCH';
  deterministic_message?: string;
  suggestions?: string[];
};

type SearchError = {
  message?: string;
  error?: {
    status_code?: number;
  };
  response?: {
    status?: number;
  };
};

const SUPPORTED_FILE_TYPES: ReadonlySet<NonNullable<SourceReference['file_type']>> = new Set([
  'pdf',
  'txt',
  'jpg',
  'png',
  'mp3',
  'mp4',
]);

const isSupportedFileType = (value: string): value is NonNullable<SourceReference['file_type']> => {
  return SUPPORTED_FILE_TYPES.has(value as NonNullable<SourceReference['file_type']>);
};

const isNotFoundSearchError = (error: unknown): error is SearchError => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const candidate = error as SearchError;
  return candidate.error?.status_code === 404 || candidate.response?.status === 404;
};

const mapDocumentTypeToFileType = (documentType?: string): NonNullable<SourceReference['file_type']> => {
  const normalized = documentType?.toLowerCase();
  if (normalized && isSupportedFileType(normalized)) {
    return normalized;
  }

  return 'txt';
};

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }

  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
    return error.message;
  }

  return 'Search failed';
};

const getResearchDocumentIds = (): string[] => {
  const raw = process.env.NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS;
  if (!raw) {
    return [];
  }

  return raw
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
};

export class SearchService {
  private readonly basePath = '/search';

  /**
   * Perform a search query
   */
  async search(request: SearchRequest): Promise<APIResponse<SearchResult>> {
    try {
      const researchDocumentIds = getResearchDocumentIds();
      const selectedDocumentIds =
        request.filters?.document_ids && request.filters.document_ids.length > 0
          ? request.filters.document_ids
          : researchDocumentIds;

      // Transform request to match backend expectations
      const backendRequest = {
        query: request.query,
        search_type: 'hybrid', // Default to hybrid search
        limit: request.limit || 10,
        offset: request.offset || 0,
        filters: request.filters ? {
          // Transform filters if needed
          document_ids: selectedDocumentIds,
          document_types: request.filters.modalities,
          tags: request.filters.tags,
          file_size_min: undefined,
          file_size_max: undefined,
          date_from: request.filters.date_range?.start,
          date_to: request.filters.date_range?.end,
          is_public: undefined,
          uploaded_by_user_id: undefined,
        } : selectedDocumentIds.length > 0 ? {
          document_ids: selectedDocumentIds,
        } : undefined,
        include_snippets: true,
      };

      let response: BackendSearchResponse;

      try {
        response = await apiClient.post(`${this.basePath}/hybrid`, backendRequest) as BackendSearchResponse;
      } catch (error: unknown) {
        if (!isNotFoundSearchError(error)) {
          throw error;
        }

        response = await apiClient.post(`${this.basePath}/`, {
          ...backendRequest,
          search_type: 'fulltext',
        }) as BackendSearchResponse;
      }

      // Transform backend response to match frontend expectations
      const transformedResult: SearchResult = {
        id: response.search_id || Date.now().toString(),
        query: response.query || request.query,
        answer: {
          text: '',
          sources: response.results?.map((r) => ({
            document_id: r.document_id,
            document_title: r.title,
            snippet: r.content_preview || '',
            confidence: r.relevance_score || 0,
            file_type: mapDocumentTypeToFileType(r.document_type),
          })) || [],
          confidence: response.confidence ?? 0,
          coverage: response.coverage,
          decisionTraceId: response.decision_trace_id,
          answer_type: 'factual' as const,
          language_detected: 'en',
        },
        deterministicStatus: response.deterministic_status,
        deterministicMessage: response.deterministic_message,
        refinementSuggestions: response.suggestions,
        entities: [],
        relationships: [],
        metrics: {
          latency_ms: response.search_time_ms || 0,
          retrieval_quality: 80,
          faithfulness_score: 90,
          contextual_relevancy: 85,
          hallucination_score: 10,
          answer_relevancy: 75,
          documents_retrieved: response.total_results || 0,
          entities_found: 0,
          relationships_found: 0,
        },
        processing_time_ms: response.search_time_ms || 0,
        created_at: new Date().toISOString(),
        user_id: '',
      };

      return {
        success: true,
        data: transformedResult,
        message: 'Search completed successfully',
      };
    } catch (error: unknown) {
      console.error('Search service error:', error);
      return {
        success: false,
        data: null as any,
        message: getErrorMessage(error),
      };
    }
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
    try {
      // Backend returns suggestions array directly
      const response = await apiClient.get(`${this.basePath}/suggestions`, {
        params: { q: query, limit },
      }) as string[];

      // Transform to match expected format
      const suggestions: QuerySuggestions = {
        suggestions: response || [],
        related_queries: [],
        auto_complete: response || [],
      };

      return {
        success: true,
        data: suggestions,
        message: 'Suggestions retrieved successfully',
      };
    } catch (error: any) {
      console.error('Failed to get suggestions:', error);
      return {
        success: false,
        data: {
          suggestions: [],
          related_queries: [],
          auto_complete: [],
        },
        message: error.message || 'Failed to get suggestions',
      };
    }
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
