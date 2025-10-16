// API Response Types
export interface APIResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  errors?: string[];
  pagination?: {
    page: number;
    page_size: number;
    total: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface APIError {
  error: {
    message: string;
    status_code: number;
    type: 'validation_error' | 'processing_error' | 'auth_error' | 'rate_limit' | 'internal_error';
    details?: Record<string, any>;
    timestamp: string;
  };
}

export class APIErrorClass extends Error {
  public error: APIError['error'];

  constructor(error: APIError['error']) {
    super(error.message);
    this.name = 'APIError';
    this.error = error;
  }
}

// Base Configuration
export const API_CONFIG = {
  BASE_URL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  API_VERSION: 'v1',
  TIMEOUT_MS: 30000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY_MS: 1000,
} as const;

export const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

export const getAuthHeaders = (token: string, organizationId: string) => ({
  'Authorization': `Bearer ${token}`,
  'X-Organization-ID': organizationId,
  'X-Client-Version': '1.0.0',
});