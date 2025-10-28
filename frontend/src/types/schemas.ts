/**
 * Zod schemas for runtime type validation
 * Ensures type safety between frontend and backend API contracts
 */

import { z } from 'zod';

// ============================================================================
// Common Schemas
// ============================================================================

export const TimestampSchema = z.string().datetime();

export const PaginationSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  total_pages: z.number().int().positive().optional(),
  has_next: z.boolean(),
  has_prev: z.boolean(),
});

export const APIErrorSchema = z.object({
  error: z.object({
    message: z.string(),
    status_code: z.number().int(),
    type: z.enum(['validation_error', 'processing_error', 'auth_error', 'rate_limit', 'internal_error']),
    details: z.record(z.any()).optional(),
    timestamp: TimestampSchema,
  }),
});

// ============================================================================
// Auth Schemas
// ============================================================================

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string(),
  organization_id: z.string().uuid(),
  role: z.enum(['admin', 'user', 'viewer']),
  is_active: z.boolean(),
  created_at: TimestampSchema,
  last_login: TimestampSchema.nullable().optional(),
});

export const OrganizationSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  settings: z.record(z.any()).optional(),
  created_at: TimestampSchema,
});

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string().default('bearer'),
  expires_in: z.number().int().positive(),
  user: UserSchema,
  organization: OrganizationSchema,
});

// ============================================================================
// Document Schemas
// ============================================================================

export const FileTypeSchema = z.enum(['pdf', 'txt', 'jpg', 'png', 'mp3', 'mp4', 'docx']);

export const ProcessingStatusSchema = z.enum(['queued', 'processing', 'indexed', 'failed']);

export const DocumentSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  organization_id: z.string().uuid(),
  title: z.string(),
  filename: z.string(),
  file_type: FileTypeSchema,
  file_size: z.number().int().nonnegative(),
  processing_status: ProcessingStatusSchema,
  processing_error: z.string().nullable().optional(),
  upload_timestamp: TimestampSchema,
  processing_completed_at: TimestampSchema.nullable().optional(),
  thumbnail_url: z.string().url().nullable().optional(),
  page_count: z.number().int().positive().nullable().optional(),
  duration_seconds: z.number().nonnegative().nullable().optional(),
  extracted_text_preview: z.string().nullable().optional(),
  metadata: z.record(z.any()).default({}),
  description: z.string().nullable().optional(),
  tags: z.array(z.string()).default([]),
  custom_fields: z.record(z.any()).nullable().optional(),
});

export const DocumentListResponseSchema = z.object({
  documents: z.array(DocumentSchema),
  pagination: PaginationSchema,
});

// ============================================================================
// Upload Schemas - Backend Response Types
// ============================================================================

/**
 * Backend returns FileUploadResponse with 'id' field
 * Frontend expects DocumentUploadResponse with 'upload_id' field
 * This schema matches the BACKEND response
 */
export const FileUploadResponseSchema = z.object({
  // Backend uses 'id', not 'upload_id'
  id: z.string().uuid(),
  job_id: z.string().uuid(),
  message: z.string(),
  estimated_processing_time_seconds: z.number().nonnegative(),
  file_info: z.object({
    filename: z.string(),
    size: z.number().int().nonnegative(),
    content_type: z.string(),
  }),
});

/**
 * Frontend DocumentUploadResponse - transformed from backend response
 * This matches what the frontend components expect
 */
export const DocumentUploadResponseSchema = z.object({
  document_id: z.string().uuid(),
  upload_id: z.string().uuid(), // Mapped from backend 'id'
  title: z.string(),
  filename: z.string(),
  document_type: z.string(),
  file_size_bytes: z.number().int().nonnegative(),
  file_size_mb: z.number().nonnegative(),
  mime_type: z.string(),
  processing_status: z.string(),
  job_id: z.string().uuid().optional(),
  estimated_processing_time: z.number().nonnegative().optional(),
  quality_score: z.number().min(0).max(100).optional(),
  security_scan_result: z.object({
    scan_status: z.enum(['passed', 'failed', 'warning']),
    virus_detected: z.boolean(),
    suspicious_content: z.boolean(),
    file_integrity: z.string(),
    scan_timestamp: TimestampSchema,
    threats: z.array(z.object({
      type: z.string(),
      severity: z.enum(['low', 'medium', 'high', 'critical']),
      description: z.string(),
    })),
    warnings: z.array(z.string()),
  }).optional(),
  upload_progress: z.number().min(0).max(100),
  message: z.string(),
  created_at: TimestampSchema,
});

export const UploadProgressSchema = z.object({
  job_id: z.string().uuid(),
  status: z.enum(['queued', 'processing', 'completed', 'failed']),
  progress: z.number().min(0).max(100),
  current_step: z.string(),
  estimated_remaining_seconds: z.number().nonnegative().optional(),
  error_message: z.string().nullable().optional(),
});

// ============================================================================
// Search Schemas
// ============================================================================

export const EntityTypeSchema = z.enum(['person', 'organization', 'location', 'date', 'concept', 'technology', 'product']);

export const EntitySchema = z.object({
  id: z.string().uuid(),
  text: z.string(),
  type: EntityTypeSchema,
  confidence: z.number().min(0).max(1),
  start_position: z.number().int().nonnegative().optional(),
  end_position: z.number().int().nonnegative().optional(),
  context: z.string().optional(),
  neo4j_node_id: z.string().optional(),
});

export const SearchResultItemSchema = z.object({
  document_id: z.string().uuid(),
  title: z.string(),
  content: z.string(),
  score: z.number().min(0).max(1),
  highlights: z.array(z.string()).default([]),
  metadata: z.record(z.any()).default({}),
  file_type: FileTypeSchema,
  entities: z.array(EntitySchema).default([]),
  thumbnail_url: z.string().url().nullable().optional(),
});

export const SearchResultSchema = z.object({
  query: z.string(),
  results: z.array(SearchResultItemSchema),
  total_results: z.number().int().nonnegative(),
  search_time_ms: z.number().nonnegative(),
  facets: z.record(z.array(z.any())).optional(),
  query_id: z.string().uuid().optional(),
});

// ============================================================================
// Knowledge Graph Schemas
// ============================================================================

export const GraphNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: EntityTypeSchema,
  properties: z.record(z.any()).default({}),
  confidence: z.number().min(0).max(1).optional(),
});

export const GraphEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  label: z.string(),
  type: z.string(),
  properties: z.record(z.any()).default({}),
  confidence: z.number().min(0).max(1).optional(),
});

export const GraphDataSchema = z.object({
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  metadata: z.object({
    total_nodes: z.number().int().nonnegative(),
    total_edges: z.number().int().nonnegative(),
    query_time_ms: z.number().nonnegative(),
  }).optional(),
});

export const EntityDetailsSchema = z.object({
  entity: EntitySchema,
  relationships: z.array(z.object({
    id: z.string(),
    type: z.string(),
    target_entity: EntitySchema,
    confidence: z.number().min(0).max(1),
  })).default([]),
  documents: z.array(DocumentSchema).default([]),
  co_occurrences: z.array(EntitySchema).default([]),
});

// ============================================================================
// Analytics Schemas
// ============================================================================

export const EvaluationMetricsSchema = z.object({
  query_id: z.string().uuid(),
  answer_relevancy: z.number().min(0).max(1),
  faithfulness: z.number().min(0).max(1),
  contextual_relevancy: z.number().min(0).max(1),
  latency_ms: z.number().nonnegative(),
  retrieval_count: z.number().int().nonnegative(),
  token_count: z.number().int().nonnegative(),
  timestamp: TimestampSchema,
});

export const PerformanceAnalyticsSchema = z.object({
  time_range: z.object({
    start: TimestampSchema,
    end: TimestampSchema,
  }),
  metrics: z.object({
    total_queries: z.number().int().nonnegative(),
    average_latency_ms: z.number().nonnegative(),
    p95_latency_ms: z.number().nonnegative(),
    p99_latency_ms: z.number().nonnegative(),
    average_relevancy: z.number().min(0).max(1),
    average_faithfulness: z.number().min(0).max(1),
    error_rate: z.number().min(0).max(1),
  }),
  time_series: z.array(z.object({
    timestamp: TimestampSchema,
    query_count: z.number().int().nonnegative(),
    average_latency_ms: z.number().nonnegative(),
    error_count: z.number().int().nonnegative(),
  })).default([]),
});

// ============================================================================
// Type Inference
// ============================================================================

export type User = z.infer<typeof UserSchema>;
export type Organization = z.infer<typeof OrganizationSchema>;
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
export type Document = z.infer<typeof DocumentSchema>;
export type DocumentListResponse = z.infer<typeof DocumentListResponseSchema>;
export type FileUploadResponse = z.infer<typeof FileUploadResponseSchema>;
export type DocumentUploadResponse = z.infer<typeof DocumentUploadResponseSchema>;
export type UploadProgress = z.infer<typeof UploadProgressSchema>;
export type Entity = z.infer<typeof EntitySchema>;
export type SearchResultItem = z.infer<typeof SearchResultItemSchema>;
export type SearchResult = z.infer<typeof SearchResultSchema>;
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type GraphData = z.infer<typeof GraphDataSchema>;
export type EntityDetails = z.infer<typeof EntityDetailsSchema>;
export type EvaluationMetrics = z.infer<typeof EvaluationMetricsSchema>;
export type PerformanceAnalytics = z.infer<typeof PerformanceAnalyticsSchema>;
export type Pagination = z.infer<typeof PaginationSchema>;
export type APIError = z.infer<typeof APIErrorSchema>;
