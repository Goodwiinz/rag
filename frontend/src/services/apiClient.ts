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
        // Add auth headers if available
        const token = useAuthStore.getState().token;
        const organizationId = useAuthStore.getState().organization?.id;

        if (token && organizationId) {
          const authHeaders = getAuthHeaders(token, organizationId);
          Object.entries(authHeaders).forEach(([key, value]) => {
            config.headers.set(key, value);
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

        // Handle 401 Unauthorized
        if (error.response?.status === 401 && !originalRequest._retry) {
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
            useAuthStore.getState().logout();
            return Promise.reject(refreshError);
          }
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
      headers: {
        'Content-Type': 'multipart/form-data',
      },
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