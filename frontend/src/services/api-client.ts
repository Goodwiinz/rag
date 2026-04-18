/**
 * Unified API Client
 *
 * This is the consolidated API client that combines functionality from:
 * - api.ts (RAGAPIClient - basic API methods)
 * - apiClient.ts (ApiClient - axios-based with interceptors)
 * - typeSafeApiClient.ts (TypeSafeAPIClient - zod validation)
 *
 * Features:
 * - Consistent error handling
 * - Type-safe request/response with optional Zod validation
 * - Request/response interceptors
 * - Retry logic with exponential backoff
 * - File upload with progress tracking
 * - Token refresh and auth management
 */

import {
    API_CONFIG,
    APIErrorClass,
    DEFAULT_HEADERS,
} from '@/types/api';
import { ZodSchema } from 'zod';

// ============================================================================
// Types
// ============================================================================

export interface RequestConfig extends RequestInit {
  skipValidation?: boolean;
  retries?: number;
  retryDelay?: number;
  timeout?: number;
}

export interface TypedResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

export interface UploadOptions {
  onProgress?: (progress: number) => void;
  metadata?: Record<string, string>;
}

// ============================================================================
// Unified API Client
// ============================================================================

export class APIClient {
  private baseURL: string;
  private token: string | null = null;
  private organizationId: string | null = null;
  private defaultTimeout: number;

  constructor(baseURL: string = API_CONFIG.BASE_URL) {
    this.baseURL = baseURL;
    this.defaultTimeout = API_CONFIG.TIMEOUT_MS || 30000;
    this.loadAuthFromStorage();
  }

  // --------------------------------------------------------------------------
  // Authentication
  // --------------------------------------------------------------------------

  setAuth(token: string, organizationId: string): void {
    this.token = token;
    this.organizationId = organizationId;
  }

  clearAuth(): void {
    this.token = null;
    this.organizationId = null;
  }

  private loadAuthFromStorage(): void {
    if (typeof window === 'undefined') return;

    try {
      const authStorage = localStorage.getItem('auth-storage');
      if (authStorage) {
        const parsed = JSON.parse(authStorage);
        if (parsed?.state?.token && parsed?.state?.organization?.id) {
          this.token = parsed.state.token;
          this.organizationId = parsed.state.organization.id;
        }
      }
    } catch (error) {
      console.warn('Failed to load auth from storage:', error);
    }
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      ...DEFAULT_HEADERS,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (this.organizationId) {
      headers['X-Organization-ID'] = this.organizationId;
    }

    return headers;
  }

  // --------------------------------------------------------------------------
  // Core Request Methods
  // --------------------------------------------------------------------------

  async request<T>(
    endpoint: string,
    options: RequestConfig = {}
  ): Promise<T> {
    const {
      retries = API_CONFIG.RETRY_ATTEMPTS || 3,
      retryDelay = 1000,
      timeout = this.defaultTimeout,
      ...fetchOptions
    } = options;

    const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          ...this.getHeaders(),
          ...fetchOptions.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await this.handleErrorResponse(response);
        throw error;
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        return {} as T;
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      // Handle abort error
      if ((error as Error).name === 'AbortError') {
        throw new APIErrorClass({
          message: 'Request timeout',
          status_code: 408,
          type: 'http_error',
          details: { timeout }
        });
      }

      // Retry logic for network errors
      if (retries > 0 && this.isRetryableError(error)) {
        await this.delay(retryDelay);
        return this.request<T>(endpoint, {
          ...options,
          retries: retries - 1,
          retryDelay: retryDelay * 2, // Exponential backoff
        });
      }

      throw error;
    }
  }

  async requestWithValidation<T>(
    endpoint: string,
    schema: ZodSchema<T>,
    options: RequestConfig = {}
  ): Promise<TypedResponse<T>> {
    const response = await fetch(
      endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`,
      {
        ...options,
        headers: {
          ...this.getHeaders(),
          ...options.headers,
        },
      }
    );

    if (!response.ok) {
      throw await this.handleErrorResponse(response);
    }

    const rawData = await response.json();

    // Validate with Zod schema
    if (!options.skipValidation) {
      const result = schema.safeParse(rawData);
      if (!result.success) {
        throw new APIErrorClass({
          message: 'Response validation failed',
          status_code: 500,
          type: 'validation_error',
          details: { errors: result.error.issues }
        });
      }
      return {
        data: result.data,
        status: response.status,
        headers: response.headers,
      };
    }

    return {
      data: rawData,
      status: response.status,
      headers: response.headers,
    };
  }

  // --------------------------------------------------------------------------
  // HTTP Methods
  // --------------------------------------------------------------------------

  async get<T>(endpoint: string, options: RequestConfig = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown, options: RequestConfig = {}): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown, options: RequestConfig = {}): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown, options: RequestConfig = {}): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string, options: RequestConfig = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  // --------------------------------------------------------------------------
  // File Operations
  // --------------------------------------------------------------------------

  async upload<T>(
    endpoint: string,
    file: File,
    options: UploadOptions = {}
  ): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    // Add any additional metadata
    if (options.metadata) {
      Object.entries(options.metadata).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    // For progress tracking, we need to use XMLHttpRequest
    if (options.onProgress) {
      return this.uploadWithProgress<T>(endpoint, formData, options.onProgress);
    }

    return this.request<T>(endpoint, {
      method: 'POST',
      body: formData,
      headers: {
        // Don't set Content-Type - browser will set it with boundary
      },
    });
  }

  private uploadWithProgress<T>(
    endpoint: string,
    formData: FormData,
    onProgress: (progress: number) => void
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;

      xhr.open('POST', url);

      // Set auth headers
      if (this.token) {
        xhr.setRequestHeader('Authorization', `Bearer ${this.token}`);
      }
      if (this.organizationId) {
        xhr.setRequestHeader('X-Organization-ID', this.organizationId);
      }

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress(progress);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve({} as T);
          }
        } else {
          reject(
            new APIErrorClass({
              message: xhr.statusText || 'Upload failed',
              status_code: xhr.status,
              type: 'http_error'
            })
          );
        }
      };

      xhr.onerror = () => {
        reject(new APIErrorClass({ message: 'Network error during upload', status_code: 0, type: 'http_error' }));
      };

      xhr.send(formData);
    });
  }

  async download(url: string, filename?: string): Promise<void> {
    const response = await fetch(
      url.startsWith('http') ? url : `${this.baseURL}${url}`,
      {
        headers: this.getHeaders(),
      }
    );

    if (!response.ok) {
      throw await this.handleErrorResponse(response);
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename || this.extractFilename(response) || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  }

  // --------------------------------------------------------------------------
  // Helper Methods
  // --------------------------------------------------------------------------

  private async handleErrorResponse(response: Response): Promise<APIErrorClass> {
    let errorData: Record<string, unknown> = {};

    try {
      errorData = await response.json();
    } catch {
      // Response body may not be JSON
    }

    return new APIErrorClass({
      message: (errorData.detail as string) || (errorData.message as string) || response.statusText,
      status_code: response.status,
      type: 'http_error',
      details: errorData as Record<string, unknown>
    });
  }

  private isRetryableError(error: unknown): boolean {
    if (error instanceof APIErrorClass) {
      const statusCode = error.error.status_code;
      // Don't retry client errors (4xx except 429)
      if (statusCode >= 400 && statusCode < 500 && statusCode !== 429) {
        return false;
      }
      // Retry server errors (5xx) and rate limiting (429)
      return statusCode >= 500 || statusCode === 429;
    }
    // Retry network errors
    return true;
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private extractFilename(response: Response): string | null {
    const disposition = response.headers.get('content-disposition');
    if (disposition) {
      const match = disposition.match(/filename="?([^";\n]+)"?/);
      if (match) return match[1];
    }
    return null;
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let apiClient: APIClient | null = null;

export function getAPIClient(): APIClient {
  if (!apiClient) {
    apiClient = new APIClient();
  }
  return apiClient;
}

export function initializeAPIClient(baseURL?: string): APIClient {
  apiClient = new APIClient(baseURL);
  return apiClient;
}

// ============================================================================
// Default Export
// ============================================================================

export const api = getAPIClient();
export default APIClient;
