import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { API_CONFIG, DEFAULT_HEADERS, getAuthHeaders, APIErrorClass } from '@/types/api';
import { useAuthStore } from '@/stores/authStore';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT_MS,
      headers: DEFAULT_HEADERS,
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Check if we're sending FormData - if so, delete Content-Type to let browser set it
        if (config.data instanceof FormData) {
          console.debug('📤 FormData detected, removing Content-Type header');
          delete config.headers['Content-Type'];
        }

        // Add auth headers if available
        const authState = useAuthStore.getState();
        const token = authState.token;
        const organizationId = authState.organization?.id;
        const isAuthenticated = authState.isAuthenticated;

        // Debug logging
        console.debug('🔐 Auth Debug:', {
          url: config.url,
          method: config.method,
          hasToken: !!token,
          hasOrganizationId: !!organizationId,
          isAuthenticated,
          tokenPreview: token ? `${token.substring(0, 20)}...` : null,
          organizationId,
          currentHeaders: config.headers,
          authStateLoading: authState.isLoading,
          fullAuthState: authState
        });

        if (token) {
          const authHeaders = getAuthHeaders(token, organizationId || 'default');
          Object.entries(authHeaders).forEach(([key, value]) => {
            config.headers.set(key, value);
          });
          console.debug('✅ Auth headers added:', authHeaders, {
            hasOrganizationId: !!organizationId
          });
        } else {
          console.warn('⚠️ Missing auth data:', {
            hasToken: !!token,
            hasOrganizationId: !!organizationId,
            isAuthenticated,
            isLoading: authState.isLoading
          });
        }

        // Add request timestamp
        config.metadata = { startTime: new Date() };

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        // Log request duration
        const startTime = response.config.metadata?.startTime;
        if (startTime) {
          const duration = new Date().getTime() - startTime.getTime();
          console.debug(`API request to ${response.config.url} took ${duration}ms`);
        }

        return response;
      },
      async (error) => {
        const originalRequest = error.config;

        // Don't retry if this IS the refresh token request itself
        const isRefreshRequest = originalRequest.url?.includes('/auth/refresh');

        // Handle 401 Unauthorized
        if (error.response?.status === 401 && !originalRequest._retry && !isRefreshRequest) {
          originalRequest._retry = true;

          try {
            // Attempt to refresh token
            await useAuthStore.getState().refreshToken();

            // Retry original request with new token
            const token = useAuthStore.getState().token;
            const organizationId = useAuthStore.getState().organization?.id;

            if (token && organizationId) {
              originalRequest.headers = {
                ...originalRequest.headers,
                ...getAuthHeaders(token, organizationId),
              };
            }

            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed, logout user
            console.warn('Token refresh failed, logging out');
            useAuthStore.getState().logout();
            return Promise.reject(refreshError);
          }
        }

        // If this is the refresh endpoint failing, logout immediately
        if (isRefreshRequest && error.response?.status === 401) {
          console.warn('Refresh token expired, logging out');
          useAuthStore.getState().logout();
        }

        // Convert to APIErrorClass
        if (error.response?.data) {
          return Promise.reject(new APIErrorClass(error.response.data));
        }

        return Promise.reject(error);
      }
    );
  }

  // HTTP methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  // File upload
  async upload<T>(url: string, file: File, onProgress?: (progress: number) => void): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    const config: AxiosRequestConfig = {
      // Don't set Content-Type header manually - Axios will set it correctly for FormData
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
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

  // WebSocket connection helper
  createWebSocket(url: string): WebSocket {
    const token = useAuthStore.getState().token;
    const organizationId = useAuthStore.getState().organization?.id;

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