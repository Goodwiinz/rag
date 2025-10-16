# Data Models: Multimodal Enterprise RAG UI

**Feature**: Multimodal Enterprise RAG UI
**Date**: 2025-10-14
**Purpose**: Frontend data models and type definitions
**Status**: ✅ COMPLETED

## Overview

This document defines the TypeScript data models and interfaces required for the frontend implementation of the Multimodal Enterprise RAG UI. These models align with the existing backend API responses and provide type safety for the entire application.

---

## Core Data Models

### User and Authentication

```typescript
interface User {
  id: string;
  email: string;
  name: string;
  organization_id: string;
  role: 'admin' | 'user' | 'viewer';
  storage_quota_used: number; // bytes
  storage_quota_limit: number; // bytes
  created_at: string;
  last_login: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface LoginRequest {
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}
```

### Document Management

```typescript
interface Document {
  id: string;
  user_id: string;
  organization_id: string;
  title: string;
  filename: string;
  file_type: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  file_size: number; // bytes
  processing_status: 'queued' | 'processing' | 'indexed' | 'failed';
  processing_error?: string;
  upload_timestamp: string;
  processing_completed_at?: string;
  thumbnail_url?: string;
  page_count?: number;
  duration_seconds?: number;
  extracted_text_preview?: string;
  metadata: Record<string, any>;
}

interface DocumentUpload {
  file: File;
  id: string;
  progress: number; // 0-100
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  jobId?: string;
  documentId?: string;
}

interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

interface DocumentFilters {
  file_types?: Document['file_type'][];
  status?: Document['processing_status'][];
  date_range?: {
    start: string;
    end: string;
  };
  search_term?: string;
}
```

### Search and Query

```typescript
interface SearchRequest {
  query: string;
  filters?: {
    modalities?: ('text' | 'image' | 'audio' | 'video')[];
    document_ids?: string[];
    date_range?: {
      start: string;
      end: string;
    };
    file_types?: Document['file_type'][];
  };
  limit?: number;
  offset?: number;
}

interface SourceReference {
  document_id: string;
  document_title: string;
  snippet: string;
  confidence: number;
  page_number?: number;
  timestamp?: string;
  file_type: Document['file_type'];
  url?: string; // For direct document access
}

interface SearchAnswer {
  text: string;
  sources: SourceReference[];
  confidence: number;
  answer_type: 'factual' | 'reasoning' | 'summarization' | 'comparison';
  language_detected: string;
}

interface SearchResult {
  id: string;
  query: string;
  answer: SearchAnswer;
  entities: Entity[];
  relationships: Relationship[];
  metrics: SearchMetrics;
  processing_time_ms: number;
  created_at: string;
  user_id: string;
}

interface SearchMetrics {
  latency_ms: number;
  retrieval_quality: number; // 0-100
  faithfulness_score: number; // 0-100
  contextual_relevancy: number; // 0-100
  hallucination_score: number; // 0-100
  answer_relevancy: number; // 0-100
  documents_retrieved: number;
  entities_found: number;
  relationships_found: number;
}

interface QueryHistory {
  id: string;
  query: string;
  created_at: string;
  answer_preview: string; // First 100 characters
  has_answer: boolean;
  metrics: {
    latency_ms: number;
    quality_score: number;
  };
}

interface QuerySuggestions {
  suggestions: string[];
  related_queries: Array<{
    query: string;
    similarity: number;
  }>;
  auto_complete: string[];
}
```

### Knowledge Graph

```typescript
interface Entity {
  id: string;
  name: string;
  type: 'person' | 'organization' | 'location' | 'concept' | 'date' | 'product';
  confidence: number;
  description?: string;
  aliases: string[];
  mentions: number;
  first_seen: string;
  last_seen: string;
  document_ids: string[];
  metadata: Record<string, any>;
  position?: {
    x: number;
    y: number;
  };
  color?: string;
  size?: number;
}

interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  confidence: number;
  context: string;
  document_ids: string[];
  first_seen: string;
  last_seen: string;
  weight: number;
  metadata: Record<string, any>;
}

interface GraphData {
  nodes: Entity[];
  edges: Relationship[];
  layout: 'force' | 'hierarchical' | 'circular';
  filters: {
    entity_types?: Entity['type'][];
    min_confidence?: number;
    date_range?: {
      start: string;
      end: string;
    };
  };
}

interface GraphNodeInteraction {
  node_id: string;
  action: 'click' | 'hover' | 'select';
  timestamp: string;
  related_nodes: string[];
  context: {
    query_id?: string;
    search_context?: string;
  };
}

interface GraphFilters {
  entity_types: Entity['type'][];
  relationship_types: string[];
  min_confidence: number;
  date_range?: {
    start: string;
    end: string;
  };
  document_ids?: string[];
}
```

### Evaluation and Analytics

```typescript
interface EvaluationMetrics {
  query_id: string;
  rag_triad: {
    answer_relevancy: number; // 0-100
    faithfulness: number; // 0-100
    contextual_relevancy: number; // 0-100
  };
  performance: {
    latency_ms: number;
    documents_processed: number;
    tokens_processed: number;
    cache_hit_rate: number;
  };
  quality: {
    hallucination_score: number; // 0-100
    factual_accuracy: number; // 0-100
    coherence_score: number; // 0-100
  };
  user_feedback?: {
    helpfulness: number; // 1-5
    accuracy: number; // 1-5
    completeness: number; // 1-5
    comment?: string;
  };
  created_at: string;
}

interface PerformanceAnalytics {
  time_range: {
    start: string;
    end: string;
  };
  total_queries: number;
  average_latency_ms: number;
  success_rate: number;
  quality_scores: {
    answer_relevancy_avg: number;
    faithfulness_avg: number;
    contextual_relevancy_avg: number;
  };
  modalities_processed: Record<string, number>;
  error_rates: Record<string, number>;
  user_satisfaction: {
    average_rating: number;
    total_feedback: number;
  };
}

interface UsageAnalytics {
  user_id: string;
  time_range: {
    start: string;
    end: string;
  };
  documents_uploaded: number;
  queries_performed: number;
  storage_used_mb: number;
  processing_time_total_ms: number;
  top_queries: Array<{
    query: string;
    frequency: number;
  }>;
  file_type_distribution: Record<Document['file_type'], number>;
  search_patterns: {
    average_query_length: number;
    peak_usage_hours: number[];
    session_duration_avg_ms: number;
  };
}
```

### UI State and Layout

```typescript
interface UIState {
  activeTab: 'answers' | 'graph' | 'eval';
  sidebarOpen: boolean;
  uploadZoneActive: boolean;
  currentQuery: string;
  isProcessing: boolean;
  searchResults: SearchResult | null;
  selectedDocument: Document | null;
  selectedEntity: Entity | null;
  filters: {
    documents: DocumentFilters;
    search: SearchRequest['filters'];
    graph: GraphFilters;
  };
  viewSettings: {
    theme: 'light' | 'dark' | 'auto';
    language: string;
    results_per_page: number;
    auto_refresh: boolean;
  };
}

interface LayoutConfig {
  panels: {
    left: {
      width: number; // pixels or percentage
      collapsible: boolean;
      components: string[];
    };
    right: {
      width: number;
      collapsible: boolean;
      components: string[];
    };
  };
  responsive: {
    mobile: boolean;
    tablet: boolean;
    desktop: boolean;
  };
}

interface ComponentState {
  isLoading: boolean;
  error: string | null;
  data: any;
  lastUpdated: string;
}
```

---

## API Response Wrappers

```typescript
interface APIResponse<T> {
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

interface APIError {
  error: {
    message: string;
    status_code: number;
    type: 'validation_error' | 'processing_error' | 'auth_error' | 'rate_limit' | 'internal_error';
    details?: Record<string, any>;
    timestamp: string;
  };
}

interface UploadProgress {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number; // 0-100
  current_step: string;
  estimated_remaining_seconds?: number;
  error_message?: string;
}
```

---

## WebSocket Message Types

```typescript
interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
  user_id?: string;
  organization_id?: string;
}

// Document processing updates
interface DocumentProcessingUpdate extends WebSocketMessage {
  type: 'document_processing_update';
  payload: {
    job_id: string;
    document_id: string;
    status: Document['processing_status'];
    progress: number;
    current_step: string;
    estimated_remaining_seconds?: number;
    error_message?: string;
  };
}

// Query status updates
interface QueryStatusUpdate extends WebSocketMessage {
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

// System notifications
interface SystemNotification extends WebSocketMessage {
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

## Configuration and Constants

```typescript
// File upload constraints
export const UPLOAD_LIMITS = {
  MAX_FILE_SIZE_MB: 50,
  MAX_FILES_PER_UPLOAD: 10,
  SUPPORTED_FORMATS: ['pdf', 'txt', 'jpg', 'png', 'mp3', 'mp4'],
  CHUNK_SIZE_BYTES: 1024 * 1024, // 1MB chunks for large files
} as const;

// UI configuration
export const UI_CONFIG = {
  DEBOUNCE_DELAY_MS: 300,
  AUTO_SAVE_INTERVAL_MS: 5000,
  WEBSOCKET_RETRY_DELAY_MS: 2000,
  MAX_WEBSOCKET_RETRIES: 5,
  RESULTS_PER_PAGE: 10,
  MAX_GRAPH_NODES: 500,
  QUERY_HISTORY_LIMIT: 50,
} as const;

// Performance thresholds
export const PERFORMANCE_THRESHOLDS = {
  MAX_ACCEPTABLE_LATENCY_MS: 2000,
  MIN_ANSWER_QUALITY_SCORE: 70,
  MIN_FAITHFULNESS_SCORE: 90,
  MAX_HALLUCINATION_SCORE: 10,
  UPLOAD_PROCESSING_TIMEOUT_MS: 300000, // 5 minutes
} as const;

// Color schemes for visualization
export const ENTITY_TYPE_COLORS = {
  person: '#4F46E5',
  organization: '#059669',
  location: '#DC2626',
  concept: '#7C3AED',
  date: '#EA580C',
  product: '#0891B2',
} as const;

// Status indicators
export const STATUS_COLORS = {
  queued: '#F59E0B',
  processing: '#3B82F6',
  indexed: '#10B981',
  failed: '#EF4444',
} as const;
```

---

## Utility Types

```typescript
// Deep partial for nested updates
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

// ID-based entity lookup
type EntityById<T extends { id: string }> = Record<string, T>;

// Status union types
type ProcessingStatus = Document['processing_status'];
type FileType = Document['file_type'];
type EntityType = Entity['type'];
type TabType = UIState['activeTab'];

// API endpoint parameters
type DocumentListParams = {
  page?: number;
  page_size?: number;
  file_type?: FileType;
  status?: ProcessingStatus;
  search?: string;
};

type SearchParams = {
  query: string;
  modalities?: ('text' | 'image' | 'audio' | 'video')[];
  document_ids?: string[];
  limit?: number;
  offset?: number;
};

// Event handlers
type EventHandler<T = void> = (event: T) => void;
type AsyncEventHandler<T = void> = (event: T) => Promise<void>;

// Form data
interface UploadFormData {
  files: File[];
  metadata?: Record<string, string>;
}

interface QueryFormData {
  query: string;
  filters?: SearchRequest['filters'];
}
```

---

## Validation Schemas

```typescript
// Runtime validation for API responses (using zod or similar)
export const DocumentSchema = {
  id: 'string',
  user_id: 'string',
  title: 'string',
  file_type: ['pdf', 'txt', 'jpg', 'png', 'mp3', 'mp4'],
  file_size: 'number',
  processing_status: ['queued', 'processing', 'indexed', 'failed'],
  upload_timestamp: 'string',
};

export const SearchRequestSchema = {
  query: 'string',
  filters: {
    modalities: ['text', 'image', 'audio', 'video'],
    document_ids: ['string'],
    limit: 'number',
    offset: 'number',
  },
};

export const EntitySchema = {
  id: 'string',
  name: 'string',
  type: ['person', 'organization', 'location', 'concept', 'date', 'product'],
  confidence: 'number',
  aliases: ['string'],
  mentions: 'number',
};
```

---

## Conclusion

These data models provide a comprehensive type-safe foundation for the frontend implementation. They align with the existing backend API structure and include all necessary interfaces for the user stories defined in the specification:

1. **Document Ingestion**: `Document`, `DocumentUpload`, `UploadProgress` models
2. **Natural Language Query**: `SearchRequest`, `SearchResult`, `SourceReference` models
3. **Knowledge Graph**: `Entity`, `Relationship`, `GraphData` models
4. **Query Evaluation**: `EvaluationMetrics`, `PerformanceAnalytics` models

The models support real-time updates, error handling, and responsive design patterns required for the enterprise RAG interface.