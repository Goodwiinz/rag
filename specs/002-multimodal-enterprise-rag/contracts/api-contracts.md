# API Contracts: Multimodal Enterprise RAG UI

**Feature**: Multimodal Enterprise RAG UI
**Date**: 2025-10-14
**Purpose**: Frontend-backend API integration contracts
**Status**: ✅ COMPLETED

## Overview

This document defines the API contracts between the frontend React application and the existing FastAPI backend. All endpoints are already implemented and tested; this contract serves as the integration specification for frontend development.

---

## Base Configuration

```typescript
// API Configuration
const API_CONFIG = {
  BASE_URL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  API_VERSION: 'v1',
  TIMEOUT_MS: 30000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY_MS: 1000,
} as const;

// Default headers
const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

// Required headers for authenticated requests
const getAuthHeaders = (token: string, organizationId: string) => ({
  'Authorization': `Bearer ${token}`,
  'X-Organization-ID': organizationId,
  'X-Client-Version': '1.0.0',
});
```

---

## Authentication Endpoints

### POST `/api/v1/auth/register`
**Purpose**: User registration
**Authentication**: None

```typescript
// Request
interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  organization_name?: string;
}

// Response (201 Created)
interface RegisterResponse {
  user: User;
  message: string;
}

// Error (400 Bad Request)
interface RegisterError {
  error: {
    message: "Email already registered" | "Invalid email format" | "Password too weak";
    status_code: 400;
    type: "validation_error";
  };
}
```

### POST `/api/v1/auth/login`
**Purpose**: User authentication
**Authentication**: None

```typescript
// Request
interface LoginRequest {
  email: string;
  password: string;
}

// Response (200 OK)
interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// Error (401 Unauthorized)
interface LoginError {
  error: {
    message: "Invalid credentials";
    status_code: 401;
    type: "auth_error";
  };
}
```

### POST `/api/v1/auth/refresh`
**Purpose**: Token refresh
**Authentication**: Refresh token (cookie)

```typescript
// Request: No body required
// Headers: Cookie with refresh_token

// Response (200 OK)
interface RefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// Error (401 Unauthorized)
interface RefreshError {
  error: {
    message: "Refresh token expired";
    status_code: 401;
    type: "auth_error";
  };
}
```

### GET `/api/v1/auth/me`
**Purpose**: Get current user info
**Authentication**: Bearer token

```typescript
// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface MeResponse {
  user: User;
}

// Error (401 Unauthorized)
interface MeError {
  error: {
    message: "Invalid token";
    status_code: 401;
    type: "auth_error";
  };
}
```

---

## Document Management Endpoints

### POST `/api/v1/files/upload`
**Purpose**: Upload document files
**Authentication**: Required
**Content-Type**: `multipart/form-data`

```typescript
// Request: FormData
interface UploadRequest {
  file: File;
  metadata?: Record<string, string>;
}

// Headers:
// - Authorization: Bearer <token>
// - X-Organization-ID: <org_id>
// - Content-Type: multipart/form-data

// Response (202 Accepted)
interface UploadResponse {
  job_id: string;
  message: string;
  estimated_processing_time_seconds: number;
  file_info: {
    filename: string;
    file_size: number;
    file_type: string;
  };
}

// Error (400 Bad Request)
interface UploadError {
  error: {
    message: "File too large" | "Unsupported file type" | "Storage quota exceeded";
    status_code: 400;
    type: "validation_error";
    details: {
      max_size_mb: number;
      supported_formats: string[];
      current_quota_used: number;
      quota_limit: number;
    };
  };
}
```

### GET `/api/v1/documents`
**Purpose**: List user documents
**Authentication**: Required

```typescript
// Query Parameters
interface DocumentsListParams {
  page?: number;          // Default: 1
  page_size?: number;     // Default: 20, Max: 100
  file_type?: string;     // Comma-separated list
  status?: string;        // Comma-separated list
  search?: string;        // Search in title/filename
  date_from?: string;     // ISO 8601 date
  date_to?: string;       // ISO 8601 date
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface DocumentsListResponse {
  documents: Document[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

// Error (422 Unprocessable Entity)
interface DocumentsListError {
  error: {
    message: "Invalid query parameters";
    status_code: 422;
    type: "validation_error";
  };
}
```

### GET `/api/v1/documents/{document_id}`
**Purpose**: Get document details
**Authentication**: Required

```typescript
// Path Parameters
interface DocumentDetailsParams {
  document_id: string;
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface DocumentDetailsResponse {
  document: Document;
  extracted_content: {
    text_preview?: string;
    entities?: Entity[];
    metadata?: Record<string, any>;
  };
  processing_history: Array<{
    step: string;
    status: 'completed' | 'failed';
    timestamp: string;
    duration_ms: number;
    error_message?: string;
  }>;
}

// Error (404 Not Found)
interface DocumentNotFoundError {
  error: {
    message: "Document not found";
    status_code: 404;
    type: "not_found";
  };
}
```

### DELETE `/api/v1/documents/{document_id}`
**Purpose**: Delete document
**Authentication**: Required

```typescript
// Path Parameters
interface DeleteDocumentParams {
  document_id: string;
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (204 No Content)
// No body returned

// Error (404 Not Found)
interface DeleteDocumentError {
  error: {
    message: "Document not found";
    status_code: 404;
    type: "not_found";
  };
}
```

---

## Search and Query Endpoints

### POST `/api/v1/search`
**Purpose**: Perform natural language search
**Authentication**: Required

```typescript
// Request Body
interface SearchRequest {
  query: string;
  filters?: {
    modalities?: ('text' | 'image' | 'audio' | 'video')[];
    document_ids?: string[];
    date_range?: {
      start: string;     // ISO 8601
      end: string;       // ISO 8601
    };
    file_types?: string[];
    min_confidence?: number;  // 0-1
  };
  limit?: number;         // Default: 10, Max: 50
  offset?: number;        // Default: 0
  include_sources?: boolean;    // Default: true
  include_entities?: boolean;   // Default: true
  include_graph?: boolean;      // Default: false
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface SearchResponse {
  query_id: string;
  query: string;
  answer: {
    text: string;
    sources: SourceReference[];
    confidence: number;
    answer_type: 'factual' | 'reasoning' | 'summarization' | 'comparison';
  };
  entities: Entity[];
  metrics: SearchMetrics;
  processing_time_ms: number;
  created_at: string;
}

// Error (400 Bad Request)
interface SearchError {
  error: {
    message: "Query too short" | "Invalid filters" | "Rate limit exceeded";
    status_code: 400;
    type: "validation_error";
  };
}
```

### GET `/api/v1/search/suggestions`
**Purpose**: Get query suggestions
**Authentication**: Required

```typescript
// Query Parameters
interface SuggestionsParams {
  q: string;              // Partial query
  limit?: number;         // Default: 5
  include_history?: boolean;  // Default: true
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface SuggestionsResponse {
  suggestions: string[];
  related_queries: Array<{
    query: string;
    similarity: number;
  }>;
  auto_complete: string[];
  recent_queries: QueryHistory[];
}
```

### GET `/api/v1/search/history`
**Purpose**: Get query history
**Authentication**: Required

```typescript
// Query Parameters
interface HistoryParams {
  page?: number;          // Default: 1
  page_size?: number;     // Default: 20
  date_from?: string;     // ISO 8601
  date_to?: string;       // ISO 8601
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface HistoryResponse {
  queries: QueryHistory[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    has_next: boolean;
    has_prev: boolean;
  };
}
```

---

## Knowledge Graph Endpoints

### POST `/api/v1/knowledge_graph/entities`
**Purpose**: Get entities for query result
**Authentication**: Required

```typescript
// Request Body
interface GraphEntitiesRequest {
  query_id?: string;      // Optional: get entities for specific query
  document_ids?: string[]; // Optional: get entities for specific documents
  filters?: {
    entity_types?: Entity['type'][];
    min_confidence?: number;
    limit?: number;       // Default: 100
  };
  include_relationships?: boolean;  // Default: true
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface GraphEntitiesResponse {
  query_id?: string;
  nodes: Entity[];
  edges: Relationship[];
  layout: {
    algorithm: 'force' | 'hierarchical' | 'circular';
    positions: Record<string, { x: number; y: number }>;
  };
  metadata: {
    total_nodes: number;
    total_edges: number;
    confidence_range: { min: number; max: number };
  };
}
```

### GET `/api/v1/knowledge_graph/entities/{entity_id}`
**Purpose**: Get entity details
**Authentication**: Required

```typescript
// Path Parameters
interface EntityDetailsParams {
  entity_id: string;
}

// Query Parameters
interface EntityDetailsQuery {
  include_relationships?: boolean;  // Default: true
  include_documents?: boolean;      // Default: true
  limit?: number;                   // Default: 50
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface EntityDetailsResponse {
  entity: Entity;
  relationships: Relationship[];
  documents: Document[];
  related_entities: Array<{
    entity: Entity;
    relationship: Relationship;
    strength: number;
  }>;
  mention_contexts: Array<{
    document_id: string;
    snippet: string;
    page_number?: number;
    confidence: number;
  }>;
}
```

### POST `/api/v1/knowledge_graph/relationships`
**Purpose**: Get relationships between entities
**Authentication**: Required

```typescript
// Request Body
interface GraphRelationshipsRequest {
  entity_ids: string[];
  relationship_types?: string[];
  max_depth?: number;      // Default: 2
  limit?: number;          // Default: 100
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface GraphRelationshipsResponse {
  paths: Array<{
    entities: Entity[];
    relationships: Relationship[];
    strength: number;
    length: number;  // Number of hops
  }>;
  metadata: {
    total_paths: number;
    max_strength: number;
    avg_path_length: number;
  };
}
```

---

## Evaluation and Analytics Endpoints

### GET `/api/v1/analytics/quality/query/{query_id}`
**Purpose**: Get quality metrics for specific query
**Authentication**: Required

```typescript
// Path Parameters
interface QueryMetricsParams {
  query_id: string;
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface QueryMetricsResponse {
  query_id: string;
  rag_triad: {
    answer_relevancy: number;
    faithfulness: number;
    contextual_relevancy: number;
  };
  performance: {
    latency_ms: number;
    documents_processed: number;
    tokens_processed: number;
    cache_hit_rate: number;
  };
  quality: {
    hallucination_score: number;
    factual_accuracy: number;
    coherence_score: number;
  };
  benchmarks: {
    relevance_percentile: number;
    faithfulness_percentile: number;
    latency_percentile: number;
  };
}
```

### GET `/api/v1/analytics/performance/dashboard`
**Purpose**: Get performance dashboard data
**Authentication**: Required

```typescript
// Query Parameters
interface DashboardParams {
  time_range?: '1h' | '24h' | '7d' | '30d';  // Default: 24h
  granularity?: 'minute' | 'hour' | 'day';   // Default: hour
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface DashboardResponse {
  time_series: Array<{
    timestamp: string;
    query_count: number;
    avg_latency_ms: number;
    avg_quality_score: number;
    error_rate: number;
  }>;
  summary: {
    total_queries: number;
    avg_latency_ms: number;
    success_rate: number;
    avg_quality_score: number;
    unique_users: number;
  };
  top_queries: Array<{
    query: string;
    frequency: number;
    avg_quality_score: number;
  }>;
  modality_distribution: Record<string, number>;
}
```

### POST `/api/v1/analytics/quality/feedback`
**Purpose**: Submit user feedback for query
**Authentication**: Required

```typescript
// Request Body
interface FeedbackRequest {
  query_id: string;
  helpfulness: number;      // 1-5
  accuracy: number;         // 1-5
  completeness: number;     // 1-5
  comment?: string;
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (201 Created)
interface FeedbackResponse {
  feedback_id: string;
  message: "Feedback submitted successfully";
}

// Error (400 Bad Request)
interface FeedbackError {
  error: {
    message: "Invalid feedback data" | "Query not found";
    status_code: 400;
    type: "validation_error";
  };
}
```

---

## Processing and Jobs Endpoints

### GET `/api/v1/processing/jobs/{job_id}`
**Purpose**: Get processing job status
**Authentication**: Required

```typescript
// Path Parameters
interface JobStatusParams {
  job_id: string;
}

// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;         // 0-100
  current_step: string;
  estimated_remaining_seconds?: number;
  started_at: string;
  updated_at: string;
  result?: {
    document_id: string;
    processing_summary: Record<string, any>;
  };
  error_message?: string;
  retry_count: number;
}
```

### GET `/api/v1/workers/status`
**Purpose**: Get system workers status
**Authentication**: Required (admin only)

```typescript
// Headers: Authorization: Bearer <token>, X-Organization-ID: <org_id>

// Response (200 OK)
interface WorkersStatusResponse {
  workers: Array<{
    name: string;
    status: 'active' | 'idle' | 'error';
    current_tasks: number;
    max_tasks: number;
    memory_usage_mb: number;
    cpu_usage_percent: number;
    last_heartbeat: string;
  }>;
  queues: Array<{
    name: string;
    pending_tasks: number;
    processing_tasks: number;
    failed_tasks: number;
  }>;
  system: {
    total_workers: number;
    active_workers: number;
    uptime_seconds: number;
    version: string;
  };
}
```

---

## WebSocket Connection

### Connection Endpoint: `ws://localhost:8000/ws`
**Purpose**: Real-time updates for processing and queries
**Authentication**: JWT token as query parameter

```typescript
// Connection URL
const wsUrl = `${API_CONFIG.BASE_URL.replace('http', 'ws')}/ws?token=${token}&organization_id=${orgId}`;

// Message Types
interface WebSocketMessage {
  type: 'document_processing_update' | 'query_status_update' | 'system_notification';
  payload: any;
  timestamp: string;
}

// Document Processing Update
interface DocumentProcessingUpdate {
  type: 'document_processing_update';
  payload: {
    job_id: string;
    document_id: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    progress: number;
    current_step: string;
    estimated_remaining_seconds?: number;
    error_message?: string;
  };
}

// Query Status Update
interface QueryStatusUpdate {
  type: 'query_status_update';
  payload: {
    query_id: string;
    status: 'processing' | 'completed' | 'failed';
    progress: number;
    current_step: string;
    result?: SearchResult;
    error_message?: string;
  };
}

// System Notification
interface SystemNotification {
  type: 'system_notification';
  payload: {
    level: 'info' | 'warning' | 'error';
    title: string;
    message: string;
    action_url?: string;
    persistent: boolean;
  };
}
```

---

## Error Handling Patterns

### Standard Error Response Format
```typescript
interface StandardError {
  error: {
    message: string;
    status_code: number;
    type: 'validation_error' | 'processing_error' | 'auth_error' | 'rate_limit' | 'not_found' | 'internal_error';
    details?: Record<string, any>;
    timestamp: string;
    request_id: string;
  };
}
```

### Rate Limiting Headers
```typescript
interface RateLimitHeaders {
  'X-RateLimit-Limit': string;      // Total limit
  'X-RateLimit-Remaining': string;  // Remaining requests
  'X-RateLimit-Reset': string;      // Unix timestamp when limit resets
  'Retry-After': string;            // Seconds to wait (on 429)
}
```

### Common HTTP Status Codes
- **200 OK**: Successful request
- **201 Created**: Resource created successfully
- **202 Accepted**: Request accepted for processing
- **204 No Content**: Successful deletion
- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Authentication required/invalid
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation errors
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

---

## Client Implementation Examples

### API Client Class
```typescript
class RAGAPIClient {
  private baseURL: string;
  private token: string | null = null;
  private organizationId: string | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  setAuth(token: string, organizationId: string) {
    this.token = token;
    this.organizationId = organizationId;
  }

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

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || 'API request failed');
    }

    return response.json();
  }

  // Authentication methods
  async login(email: string, password: string): Promise<LoginResponse> {
    return this.request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request<UploadResponse>('/files/upload', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  async search(query: string, filters?: SearchRequest['filters']): Promise<SearchResponse> {
    return this.request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({ query, filters }),
    });
  }

  async getDocuments(params?: DocumentsListParams): Promise<DocumentsListResponse> {
    const queryString = new URLSearchParams(params as any).toString();
    return this.request<DocumentsListResponse>(`/documents?${queryString}`);
  }
}
```

### WebSocket Manager
```typescript
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners: Map<string, Function[]> = new Map();

  connect(url: string) {
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.emit(message.type, message.payload);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.attemptReconnect(url);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  private emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(callback => callback(data));
  }

  private attemptReconnect(url: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`WebSocket reconnect attempt ${this.reconnectAttempts}`);
        this.connect(url);
      }, 2000 * this.reconnectAttempts);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

---

## Testing Strategies

### Mock API Responses
```typescript
// Mock data for testing
const mockSearchResponse: SearchResponse = {
  query_id: "test-query-123",
  query: "What are the main security risks?",
  answer: {
    text: "Based on the documents, the main security risks include...",
    sources: [
      {
        document_id: "doc-1",
        document_title: "Security Policy 2024",
        snippet: "Security risks include unauthorized access...",
        confidence: 0.95,
        page_number: 5,
      }
    ],
    confidence: 0.92,
    answer_type: "factual",
  },
  entities: [
    {
      id: "entity-1",
      name: "unauthorized access",
      type: "concept",
      confidence: 0.89,
      aliases: ["unauthorized entry"],
      mentions: 15,
      first_seen: "2024-01-01T00:00:00Z",
      last_seen: "2024-10-14T00:00:00Z",
      document_ids: ["doc-1", "doc-3"],
      metadata: {},
    }
  ],
  metrics: {
    latency_ms: 1250,
    retrieval_quality: 88,
    faithfulness_score: 94,
    contextual_relevancy: 91,
    hallucination_score: 5,
    answer_relevancy: 92,
    documents_retrieved: 3,
    entities_found: 8,
    relationships_found: 12,
  },
  processing_time_ms: 1580,
  created_at: "2024-10-14T10:30:00Z",
};
```

### Integration Testing
```typescript
// Example integration test
describe('API Integration', () => {
  let apiClient: RAGAPIClient;

  beforeEach(() => {
    apiClient = new RAGAPIClient('http://localhost:8000');
    apiClient.setAuth('test-token', 'test-org');
  });

  test('should search documents successfully', async () => {
    const result = await apiClient.search('test query');

    expect(result).toHaveProperty('query_id');
    expect(result).toHaveProperty('answer');
    expect(result.answer).toHaveProperty('text');
    expect(result.answer).toHaveProperty('sources');
    expect(result).toHaveProperty('metrics');
  });

  test('should handle upload errors gracefully', async () => {
    const largeFile = new File(['content'], 'large.pdf', { type: 'application/pdf' });
    Object.defineProperty(largeFile, 'size', { value: 100 * 1024 * 1024 }); // 100MB

    await expect(apiClient.uploadDocument(largeFile)).rejects.toThrow('File too large');
  });
});
```

---

## Conclusion

These API contracts provide comprehensive integration specifications for the frontend development. All endpoints are implemented and tested in the existing backend, ensuring a smooth integration process for the React application.

Key benefits of these contracts:
1. **Type Safety**: Full TypeScript support with detailed interfaces
2. **Error Handling**: Standardized error response format
3. **Real-time Updates**: WebSocket integration for live processing status
4. **Performance**: Optimized endpoints with pagination and filtering
5. **Security**: Comprehensive authentication and authorization support