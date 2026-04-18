import { getPublicApiBaseUrl } from '@/utils/publicEndpoints';

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
    type: 'validation_error' | 'processing_error' | 'auth_error' | 'rate_limit' | 'internal_error' | 'http_error';
    details?: Record<string, any>;
    timestamp?: string;
    silent?: boolean;  // If true, don't show console errors (used for optional endpoints that may not exist)
  };
}

export class APIErrorClass extends Error {
  public error: APIError['error'];

  constructor(error: APIError['error']) {
    super(error.message);
    this.name = 'APIError';
    // Add timestamp if missing
    this.error = {
      ...error,
      timestamp: error.timestamp || new Date().toISOString(),
    };
  }
}

// Base Configuration
const normalizeApiBaseUrl = (rawBaseUrl?: string): string => {
  const trimmed = (rawBaseUrl || '').trim();

  // Default to Next.js rewrite path to avoid CORS/mixed-content issues.
  if (!trimmed) return getPublicApiBaseUrl('/api/v1');

  // If already versioned, keep as-is.
  if (/\/api\/v[0-9]+\/?$/.test(trimmed)) {
    return trimmed.replace(/\/$/, '');
  }

  return `${trimmed.replace(/\/$/, '')}/api/v1`;
};

export const API_CONFIG = {
  BASE_URL: normalizeApiBaseUrl(
    process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL
  ),
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
