/**
 * @deprecated This file is deprecated. Please migrate to the new unified API client.
 * Import from '@/services/api-client' instead.
 *
 * Migration guide:
 * - Replace `apiClient` with `getAPIClient()` or `api` from api-client
 * - Use `api.get()`, `api.post()`, etc. for direct HTTP methods
 * - The new client includes retry logic, timeout handling, and better error types
 */

import {
  APIErrorClass,
  API_CONFIG,
  DEFAULT_HEADERS,
  Document,
  DocumentListResponse,
  EntityDetails,
  EvaluationMetrics,
  GraphData,
  LoginRequest,
  PerformanceAnalytics,
  QueryHistory,
  QuerySuggestions,
  RegisterRequest,
  SearchRequest,
  SearchResult,
  UploadProgress,
  User,
  UserFeedback,
  getAuthHeaders,
} from '@/types';

/** Inline response types for deprecated auth methods */
interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

interface AuthResponse {
  message: string;
  user?: User;
}

export class RAGAPIClient {
  private baseURL: string;
  private token: string | null = null;
  private organizationId: string | null = null;

  constructor(baseURL: string = API_CONFIG.BASE_URL) {
    this.baseURL = baseURL;
  }

  /**
   * Set authentication credentials
   */
  setAuth(token: string, organizationId: string): void {
    this.token = token;
    this.organizationId = organizationId;
  }

  /**
   * Clear authentication credentials
   */
  clearAuth(): void {
    this.token = null;
    this.organizationId = null;
  }

  /**
   * Make authenticated API request
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;

    const headers = {
      ...DEFAULT_HEADERS,
      ...(this.token &&
        this.organizationId &&
        getAuthHeaders(this.token, this.organizationId)),
      ...options.headers,
    };

    console.log('API Request:', {
      method: options.method || 'GET',
      url,
      hasToken: !!this.token,
      hasOrgId: !!this.organizationId,
      headers: Object.keys(headers),
    });

    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      API_CONFIG.TIMEOUT_MS
    );

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      console.log('API Response:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        url: response.url,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));

        // Handle authentication errors with more specific messages
        if (response.status === 401 || response.status === 403) {
          const authError = {
            message: 'Could not validate credentials. Please log in again.',
            status_code: response.status,
            type: 'auth_error' as const,
            timestamp: new Date().toISOString(),
          };
          throw new APIErrorClass(errorData.error || authError);
        }

        throw new APIErrorClass(
          errorData.error || {
            message: `HTTP ${response.status}: ${response.statusText}`,
            status_code: response.status,
            type: 'internal_error',
            timestamp: new Date().toISOString(),
          }
        );
      }

      const jsonResponse = await response.json();
      console.log('Parsed JSON response:', jsonResponse);
      return jsonResponse;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof APIErrorClass) {
        throw error;
      }

      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new APIErrorClass({
            message: 'Request timeout',
            status_code: 408,
            type: 'internal_error',
            timestamp: new Date().toISOString(),
          });
        }
        throw new APIErrorClass({
          message: error.message,
          status_code: 500,
          type: 'internal_error',
          timestamp: new Date().toISOString(),
        });
      }

      throw new APIErrorClass({
        message: 'Unknown error occurred',
        status_code: 500,
        type: 'internal_error',
        timestamp: new Date().toISOString(),
      });
    }
  }

  /**
   * Retry request with exponential backoff
   */
  private async requestWithRetry<T>(
    endpoint: string,
    options: RequestInit = {},
    attempts: number = API_CONFIG.RETRY_ATTEMPTS
  ): Promise<T> {
    try {
      return await this.request<T>(endpoint, options);
    } catch (error) {
      if (attempts <= 1 || this.isNonRetryableError(error)) {
        throw error;
      }

      const delay =
        API_CONFIG.RETRY_DELAY_MS * (API_CONFIG.RETRY_ATTEMPTS - attempts + 1);
      await new Promise((resolve) => setTimeout(resolve, delay));

      return this.requestWithRetry<T>(endpoint, options, attempts - 1);
    }
  }

  /**
   * Check if error should not be retried
   */
  private isNonRetryableError(error: any): boolean {
    if (error instanceof APIErrorClass) {
      const { status_code } = error.error;
      return (
        status_code === 400 ||
        status_code === 401 ||
        status_code === 403 ||
        status_code === 404
      );
    }
    return false;
  }

  // Authentication Methods

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    return this.requestWithRetry<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  }

  async register(userData: RegisterRequest): Promise<AuthResponse> {
    return this.requestWithRetry<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async refreshToken(): Promise<LoginResponse> {
    return this.requestWithRetry<LoginResponse>('/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    });
  }

  async getCurrentUser(): Promise<{ user: User }> {
    return this.requestWithRetry<{ user: User }>('/auth/me');
  }

  // Document Management Methods

  async uploadDocument(
    file: File,
    metadata?: Record<string, string>
  ): Promise<{
    job_id: string;
    message: string;
    estimated_processing_time_seconds: number;
    file_info: any;
  }> {
    const formData = new FormData();
    formData.append('file', file);

    if (metadata) {
      Object.entries(metadata).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    return this.requestWithRetry('/files/upload', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  async getDocuments(params?: {
    page?: number;
    page_size?: number;
    file_type?: string;
    status?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<DocumentListResponse> {
    // Filter out undefined values to prevent "undefined" strings in query params
    const filteredParams: Record<string, string> = {};
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          filteredParams[key] = String(value);
        }
      });
    }

    const queryParams = new URLSearchParams(filteredParams).toString();
    // Use trailing slash to avoid 307 redirect which drops Authorization header
    const endpoint = `/documents/${queryParams ? `?${queryParams}` : ''}`;

    // For development, use mock service directly to ensure documents are visible
    try {
      const { mockDocumentService } = await import('./mockDocumentService');
      return mockDocumentService.getDocuments(params || {});
    } catch (mockError) {
      // If mock service fails, try real backend
      console.warn('Mock service failed, trying real backend:', mockError);
      try {
        return await this.requestWithRetry<DocumentListResponse>(endpoint);
      } catch (backendError) {
        console.warn(
          'Backend also failed, no documents available:',
          backendError
        );
        // Return empty result
        return {
          documents: [],
          pagination: {
            page: 1,
            page_size: 20,
            total: 0,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
        };
      }
    }
  }

  async getDocument(
    documentId: string
  ): Promise<{
    document: Document;
    extracted_content: any;
    processing_history: any[];
  }> {
    return this.requestWithRetry(`/documents/${documentId}`);
  }

  async deleteDocument(documentId: string): Promise<void> {
    return this.requestWithRetry(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  async getJobStatus(jobId: string): Promise<UploadProgress> {
    return this.requestWithRetry(`/processing/jobs/${jobId}`);
  }

  async retryDocumentProcessing(
    documentId: string
  ): Promise<{ job_id: string; message: string }> {
    return this.requestWithRetry(`/processing/documents/${documentId}/retry`, {
      method: 'POST',
    });
  }

  // Search and Query Methods

  async search(request: SearchRequest): Promise<SearchResult> {
    return this.requestWithRetry<SearchResult>('/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getQuerySuggestions(params: {
    q: string;
    limit?: number;
    include_history?: boolean;
  }): Promise<QuerySuggestions> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry<QuerySuggestions>(
      `/search/suggestions?${queryParams}`
    );
  }

  async getQueryHistory(params?: {
    page?: number;
    page_size?: number;
    date_from?: string;
    date_to?: string;
  }): Promise<{ queries: QueryHistory[]; pagination: any }> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry(`/search/history?${queryParams}`);
  }

  // Knowledge Graph Methods

  async getGraphData(request: {
    query_id?: string;
    document_ids?: string[];
    filters?: {
      entity_types?: string[];
      min_confidence?: number;
      limit?: number;
    };
    include_relationships?: boolean;
  }): Promise<GraphData> {
    return this.requestWithRetry<GraphData>('/knowledge_graph/entities', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getEntityDetails(
    entityId: string,
    params?: {
      include_relationships?: boolean;
      include_documents?: boolean;
      limit?: number;
    }
  ): Promise<EntityDetails> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry<EntityDetails>(
      `/knowledge_graph/entities/${entityId}?${queryParams}`
    );
  }

  async getRelationships(request: {
    entity_ids: string[];
    relationship_types?: string[];
    max_depth?: number;
    limit?: number;
  }): Promise<any> {
    return this.requestWithRetry('/knowledge_graph/relationships', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Evaluation and Analytics Methods

  async getQueryMetrics(queryId: string): Promise<EvaluationMetrics> {
    return this.requestWithRetry<EvaluationMetrics>(
      `/analytics/quality/query/${queryId}`
    );
  }

  async getDashboardData(params?: {
    time_range?: '1h' | '24h' | '7d' | '30d';
    granularity?: 'minute' | 'hour' | 'day';
  }): Promise<PerformanceAnalytics> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry<PerformanceAnalytics>(
      `/analytics/performance/dashboard?${queryParams}`
    );
  }

  async submitFeedback(
    feedback: UserFeedback
  ): Promise<{ feedback_id: string; message: string }> {
    return this.requestWithRetry('/feedback', {
      method: 'POST',
      body: JSON.stringify(feedback),
    });
  }

  async getWorkersStatus(): Promise<any> {
    return this.requestWithRetry('/workers/status');
  }

  // Utility Methods

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.requestWithRetry('/health');
  }

  async getSystemInfo(): Promise<any> {
    return this.requestWithRetry('/debug/info');
  }
}

// Create and export singleton instance
export const apiClient = new RAGAPIClient();

// Export convenience functions
export const setAuth = (token: string, organizationId: string) => {
  apiClient.setAuth(token, organizationId);
};

export const clearAuth = () => {
  apiClient.clearAuth();
};

export default apiClient;
