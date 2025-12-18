/**
 * Type-safe API client with runtime validation
 * Provides type safety and runtime checking for all API calls
 */

import { ZodSchema } from 'zod';
import { APIErrorClass, API_CONFIG, DEFAULT_HEADERS, getAuthHeaders } from '@/types/api';
import * as schemas from '@/types/schemas';
import { validate, buildSearchParams, extractErrorMessage } from '@/lib/typeGuards';

// ============================================================================
// Type-Safe API Client Configuration
// ============================================================================

export interface RequestConfig extends RequestInit {
  skipValidation?: boolean;
  retries?: number;
  retryDelay?: number;
}

export interface TypedResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

// ============================================================================
// Type-Safe API Client
// ============================================================================

export class TypeSafeAPIClient {
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
   * Make typed and validated API request
   */
  private async requestWithValidation<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    options: RequestConfig = {}
  ): Promise<TypedResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;

    const headers = {
      ...DEFAULT_HEADERS,
      ...(this.token &&
        this.organizationId &&
        getAuthHeaders(this.token, this.organizationId)),
      ...options.headers,
    };

    // Remove Content-Type for FormData
    if (options.body instanceof FormData) {
      delete (headers as any)['Content-Type'];
    }

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

      // Skip validation if requested
      if (options.skipValidation) {
        return {
          data: jsonResponse as T,
          status: response.status,
          headers: response.headers,
        };
      }

      // Validate response against schema
      const validated = validate(schema, jsonResponse);

      if (!validated.success) {
        console.error('Response validation failed:', validated.error);
        throw new APIErrorClass({
          message: `Invalid API response format: ${validated.error.message}`,
          status_code: 500,
          type: 'internal_error',
          timestamp: new Date().toISOString(),
          details: { validationErrors: validated.error.errors },
        });
      }

      return {
        data: validated.data,
        status: response.status,
        headers: response.headers,
      };
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
          message: extractErrorMessage(error),
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
    schema: ZodSchema<T>,
    options: RequestConfig = {}
  ): Promise<TypedResponse<T>> {
    const maxRetries = options.retries ?? API_CONFIG.RETRY_ATTEMPTS;
    const retryDelay = options.retryDelay ?? API_CONFIG.RETRY_DELAY_MS;

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await this.requestWithValidation(endpoint, schema, options);
      } catch (error) {
        lastError = error as Error;

        // Don't retry on client errors
        if (error instanceof APIErrorClass) {
          const { status_code } = error.error;
          if (status_code >= 400 && status_code < 500 && status_code !== 408) {
            throw error;
          }
        }

        // Don't retry on last attempt
        if (attempt === maxRetries) {
          break;
        }

        // Wait before retrying with exponential backoff
        const delay = retryDelay * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    throw lastError;
  }

  // ============================================================================
  // Typed HTTP Methods
  // ============================================================================

  async get<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    options: RequestConfig = {}
  ): Promise<T> {
    const response = await this.requestWithRetry(endpoint, schema, {
      ...options,
      method: 'GET',
    });
    return response.data;
  }

  async post<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    data?: any,
    options: RequestConfig = {}
  ): Promise<T> {
    const body =
      data instanceof FormData ? data : data ? JSON.stringify(data) : undefined;

    const response = await this.requestWithRetry(endpoint, schema, {
      ...options,
      method: 'POST',
      body,
    });
    return response.data;
  }

  async put<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    data?: any,
    options: RequestConfig = {}
  ): Promise<T> {
    const response = await this.requestWithRetry(endpoint, schema, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
    return response.data;
  }

  async patch<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    data?: any,
    options: RequestConfig = {}
  ): Promise<T> {
    const response = await this.requestWithRetry(endpoint, schema, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
    return response.data;
  }

  async delete<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    options: RequestConfig = {}
  ): Promise<T> {
    const response = await this.requestWithRetry(endpoint, schema, {
      ...options,
      method: 'DELETE',
    });
    return response.data;
  }

  // ============================================================================
  // Convenience Methods with Built-in Schemas
  // ============================================================================

  /**
   * Authentication Methods
   */
  async login(credentials: {
    email: string;
    password: string;
  }): Promise<schemas.LoginResponse> {
    return this.post('/auth/login', schemas.LoginResponseSchema, credentials);
  }

  async getCurrentUser(): Promise<schemas.User> {
    const response = await this.get(
      '/auth/me',
      schemas.UserSchema.transform((data: any) => data.user || data)
    );
    return response;
  }

  /**
   * Document Management Methods
   */
  async getDocuments(params?: {
    page?: number;
    page_size?: number;
    file_type?: string;
    status?: string;
    search?: string;
  }): Promise<schemas.DocumentListResponse> {
    const searchParams = buildSearchParams(params || {});
    const endpoint = `/documents${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;

    return this.get(endpoint, schemas.DocumentListResponseSchema);
  }

  async getDocument(documentId: string): Promise<schemas.Document> {
    const response = await this.get(
      `/documents/${documentId}`,
      schemas.DocumentSchema.transform((data: any) => data.document || data)
    );
    return response;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.delete(
      `/documents/${documentId}`,
      schemas.z.object({ message: schemas.z.string() }).transform(() => undefined)
    );
  }

  /**
   * Upload Methods with Response Transformation
   */
  async uploadDocument(
    file: File,
    metadata?: Record<string, string>
  ): Promise<schemas.DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    if (metadata) {
      Object.entries(metadata).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    // Backend returns FileUploadResponse, we transform it
    const backendResponse = await this.post(
      '/files/upload',
      schemas.FileUploadResponseSchema,
      formData
    );

    // Transform backend response to frontend expected format
    return {
      document_id: backendResponse.id,
      upload_id: backendResponse.id,
      title: backendResponse.file_info.filename,
      filename: backendResponse.file_info.filename,
      document_type: backendResponse.file_info.content_type,
      file_size_bytes: backendResponse.file_info.size,
      file_size_mb: backendResponse.file_info.size / (1024 * 1024),
      mime_type: backendResponse.file_info.content_type,
      processing_status: 'queued',
      job_id: backendResponse.job_id,
      estimated_processing_time: backendResponse.estimated_processing_time_seconds,
      upload_progress: 0,
      message: backendResponse.message,
      created_at: new Date().toISOString(),
    };
  }

  async getJobStatus(jobId: string): Promise<schemas.UploadProgress> {
    return this.get(`/processing/jobs/${jobId}`, schemas.UploadProgressSchema);
  }

  /**
   * Search Methods
   */
  async search(request: {
    query: string;
    filters?: any;
    limit?: number;
  }): Promise<schemas.SearchResult> {
    return this.post('/search', schemas.SearchResultSchema, request);
  }

  /**
   * Knowledge Graph Methods
   */
  async getGraphData(request: {
    query_id?: string;
    document_ids?: string[];
    filters?: any;
  }): Promise<schemas.GraphData> {
    return this.post('/knowledge_graph/entities', schemas.GraphDataSchema, request);
  }

  async getEntityDetails(
    entityId: string,
    params?: {
      include_relationships?: boolean;
      include_documents?: boolean;
    }
  ): Promise<schemas.EntityDetails> {
    const searchParams = buildSearchParams(params || {});
    return this.get(
      `/knowledge_graph/entities/${entityId}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`,
      schemas.EntityDetailsSchema
    );
  }

  /**
   * Analytics Methods
   */
  async getQueryMetrics(queryId: string): Promise<schemas.EvaluationMetrics> {
    // Note: This endpoint doesn't exist in backend yet. Using search analytics instead.
    return this.get(
      `/analytics/quality/analytics?query_id=${queryId}`,
      schemas.EvaluationMetricsSchema
    );
  }

  async getDashboardData(params?: {
    time_range?: string;
    granularity?: string;
  }): Promise<schemas.PerformanceAnalytics> {
    const searchParams = buildSearchParams(params || {});
    return this.get(
      `/analytics/performance/dashboard${searchParams.toString() ? `?${searchParams.toString()}` : ''}`,
      schemas.PerformanceAnalyticsSchema
    );
  }

  /**
   * Health Check
   */
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.get(
      '/health',
      schemas.z.object({
        status: schemas.z.string(),
        timestamp: schemas.TimestampSchema,
      })
    );
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

export const typeSafeApiClient = new TypeSafeAPIClient();

export default typeSafeApiClient;
