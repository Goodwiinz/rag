/**
 * @deprecated This file is deprecated. Please migrate to the new unified API client.
 * Import from '@/services/api-client' instead.
 *
 * Migration guide:
 * - Replace `apiClient` imports with `getAPIClient()` or `api` from api-client
 * - The new client has similar methods (get, post, put, patch, delete, upload)
 * - Includes retry logic, timeout handling, and better error types
 */

import { createClient } from '@/lib/supabase/client';
import {
  API_CONFIG,
  APIErrorClass,
  DEFAULT_HEADERS,
  getAuthHeaders,
} from '@/types/api';
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

class ApiClient {
  public client: AxiosInstance;
  public longTimeoutClient: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT_MS,
      headers: DEFAULT_HEADERS,
    });

    // Create a client with longer timeout for long-running operations
    this.longTimeoutClient = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: 300000, // 5 minutes
      headers: DEFAULT_HEADERS,
    });

    this.setupInterceptors();
    this.setupLongTimeoutInterceptors();
  }

  private async getAuthFromSession() {
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const { useAuthStore } = await import('@/stores/authStore');
      const organizationId = useAuthStore.getState().organization?.id;

      return {
        token: session?.access_token ?? null,
        organizationId: organizationId ?? null,
        isAuthenticated: !!session,
      };
    } catch {
      return { token: null, organizationId: null, isAuthenticated: false };
    }
  }

  private setupInterceptors() {
    // Request interceptor — get token from Supabase session
    this.client.interceptors.request.use(
      async (config) => {
        if (config.data instanceof FormData) {
          delete config.headers['Content-Type'];
        }

        const { token, organizationId } = await this.getAuthFromSession();

        if (token) {
          const authHeaders = getAuthHeaders(
            token,
            organizationId || 'default'
          );
          Object.entries(authHeaders).forEach(([key, value]) => {
            config.headers.set(key, value);
          });
        }

        config.metadata = { startTime: new Date() };
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor — on 401, sign out (Supabase middleware handles refresh)
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error) => {
        if (error.response?.status === 401 && !error.config?._retry) {
          error.config._retry = true;
          const { useAuthStore } = await import('@/stores/authStore');
          useAuthStore.getState().signOut();
        }

        // Convert to APIErrorClass
        if (error.response?.data) {
          const errorData = error.response.data;

          if (
            errorData.error &&
            typeof errorData.error === 'object' &&
            !Array.isArray(errorData.error)
          ) {
            const normalizedMessage = (
              errorData.error.message ||
              error.message ||
              ''
            ).toLowerCase();
            const isServiceUnavailable =
              (errorData.error.status_code || error.response.status || 500) ===
                503 ||
              normalizedMessage.includes('service unavailable') ||
              normalizedMessage.includes('circuit breaker');
            const errorPayload = {
              message: errorData.error.message || 'An error occurred',
              status_code:
                errorData.error.status_code || error.response.status || 500,
              type: errorData.error.type || 'http_error',
              details: errorData.error.details,
              timestamp: errorData.error.timestamp,
              silent: errorData.error.silent ?? isServiceUnavailable,
            };
            return Promise.reject(new APIErrorClass(errorPayload));
          }

          const errorObj = {
            message:
              errorData.message ||
              errorData.detail ||
              error.message ||
              'An error occurred',
            status_code: error.response.status || 500,
            type: 'http_error' as const,
            details: errorData,
            timestamp: new Date().toISOString(),
            silent: error.response.status === 404,
          };

          return Promise.reject(new APIErrorClass(errorObj));
        }

        return Promise.reject(error);
      }
    );
  }

  private setupLongTimeoutInterceptors(): void {
    // Request interceptor — same Supabase session logic as main client
    this.longTimeoutClient.interceptors.request.use(
      async (config) => {
        const { token, organizationId } = await this.getAuthFromSession();

        if (token) {
          const authHeaders = getAuthHeaders(
            token,
            organizationId || 'default'
          );
          Object.entries(authHeaders).forEach(([key, value]) => {
            config.headers.set(key, value);
          });
        }

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor — on 401, sign out
    this.longTimeoutClient.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error) => {
        if (error.response?.status === 401 && !error.config?._retry) {
          error.config._retry = true;
          const { useAuthStore } = await import('@/stores/authStore');
          useAuthStore.getState().signOut();
        }

        if (error.response?.data) {
          const errorData = error.response.data;

          if (
            errorData.error &&
            typeof errorData.error === 'object' &&
            !Array.isArray(errorData.error)
          ) {
            const normalizedMessage = (
              errorData.error.message ||
              error.message ||
              ''
            ).toLowerCase();
            const isServiceUnavailable =
              (errorData.error.status_code || error.response.status || 500) ===
                503 ||
              normalizedMessage.includes('service unavailable') ||
              normalizedMessage.includes('circuit breaker');
            const errorPayload = {
              message: errorData.error.message || 'An error occurred',
              status_code:
                errorData.error.status_code || error.response.status || 500,
              type: errorData.error.type || 'http_error',
              details: errorData.error.details,
              timestamp: errorData.error.timestamp,
              silent: errorData.error.silent ?? isServiceUnavailable,
            };
            return Promise.reject(new APIErrorClass(errorPayload));
          }

          const errorObj = {
            message:
              errorData.message ||
              errorData.detail ||
              error.message ||
              'An error occurred',
            status_code: error.response.status || 500,
            type: 'http_error' as const,
            details: errorData,
            timestamp: new Date().toISOString(),
          };
          return Promise.reject(new APIErrorClass(errorObj));
        }

        return Promise.reject(error);
      }
    );
  }

  // Method for long timeout requests
  async postWithLongTimeout<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.longTimeoutClient.post<T>(url, data, config);
    return response.data;
  }

  // HTTP methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async patch<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  // File upload
  async upload<T>(
    url: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    const config: AxiosRequestConfig = {
      // Don't set Content-Type header manually - Axios will set it correctly for FormData
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(progress);
        }
      },
    };

    const response = await this.client.post<T>(url, formData, config);
    return response.data;
  }

  // Download file
  async download(url: string, filename?: string): Promise<void> {
    const response = await this.client.get(url, {
      responseType: 'blob',
    });

    const blob = new Blob([response.data]);
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  }

  // WebSocket connection helper — gets token from Supabase session
  async createWebSocket(url: string): Promise<WebSocket> {
    const { token, organizationId } = await this.getAuthFromSession();

    const wsUrl = new URL(url, API_CONFIG.BASE_URL.replace('http', 'ws'));
    if (token) {
      wsUrl.searchParams.append('token', token);
    }
    if (organizationId) {
      wsUrl.searchParams.append('organizationId', organizationId);
    }

    return new WebSocket(wsUrl.toString());
  }
}

// Extend axios types for metadata
declare module 'axios' {
  interface AxiosRequestConfig {
    metadata?: {
      startTime?: Date;
    };
  }
}

export const apiClient = new ApiClient();
export default apiClient;
