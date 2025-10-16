import {
  APIResponse,
  APIError,
  APIErrorClass,
  API_CONFIG,
  DEFAULT_HEADERS,
  getAuthHeaders,
  Document,
  DocumentListResponse,
  DocumentFilters,
  UploadProgress,
  SearchRequest,
  SearchResult,
  QuerySuggestions,
  QueryHistory,
  GraphData,
  EntityDetails,
  EvaluationMetrics,
  PerformanceAnalytics,
  UserFeedback,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
  AuthResponse
} from '@/types';

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
    const url = `${this.baseURL}/api/v1${endpoint}`;

    const headers = {
      ...DEFAULT_HEADERS,
      ...(this.token && this.organizationId && getAuthHeaders(this.token, this.organizationId)),
      ...options.headers,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIErrorClass(errorData.error || {
          message: `HTTP ${response.status}: ${response.statusText}`,
          status_code: response.status,
          type: 'internal_error',
          timestamp: new Date().toISOString(),
        });
      }

      return await response.json();
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

      const delay = API_CONFIG.RETRY_DELAY_MS * (API_CONFIG.RETRY_ATTEMPTS - attempts + 1);
      await new Promise(resolve => setTimeout(resolve, delay));

      return this.requestWithRetry<T>(endpoint, options, attempts - 1);
    }
  }

  /**
   * Check if error should not be retried
   */
  private isNonRetryableError(error: any): boolean {
    if (error instanceof APIErrorClass) {
      const { status_code } = error.error;
      return status_code === 400 || status_code === 401 || status_code === 403 || status_code === 404;
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

  async uploadDocument(file: File, metadata?: Record<string, string>): Promise<{ job_id: string; message: string; estimated_processing_time_seconds: number; file_info: any }> {
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
    const queryParams = new URLSearchParams(params as any).toString();
    const endpoint = `/documents${queryParams ? `?${queryParams}` : ''}`;

    return this.requestWithRetry<DocumentListResponse>(endpoint);
  }

  async getDocument(documentId: string): Promise<{ document: Document; extracted_content: any; processing_history: any[] }> {
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

  async retryDocumentProcessing(documentId: string): Promise<{ job_id: string; message: string }> {
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
    return this.requestWithRetry<QuerySuggestions>(`/search/suggestions?${queryParams}`);
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

  async getEntityDetails(entityId: string, params?: {
    include_relationships?: boolean;
    include_documents?: boolean;
    limit?: number;
  }): Promise<EntityDetails> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry<EntityDetails>(`/knowledge_graph/entities/${entityId}?${queryParams}`);
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
    return this.requestWithRetry<EvaluationMetrics>(`/analytics/quality/query/${queryId}`);
  }

  async getDashboardData(params?: {
    time_range?: '1h' | '24h' | '7d' | '30d';
    granularity?: 'minute' | 'hour' | 'day';
  }): Promise<PerformanceAnalytics> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.requestWithRetry<PerformanceAnalytics>(`/analytics/performance/dashboard?${queryParams}`);
  }

  async submitFeedback(feedback: UserFeedback): Promise<{ feedback_id: string; message: string }> {
    return this.requestWithRetry('/analytics/quality/feedback', {
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