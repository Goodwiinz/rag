import { z } from "zod";

export const HealthCheckResponseSchema = z.object({
  status: z.string(),
  version: z.string().optional(),
  timestamp: z.string().optional(),
});

export const JobStartResponseSchema = z.object({
  job_id: z.string(),
});

export const ToolExecutionSchema = z.object({
  id: z.string(),
  tool_name: z.string(),
  tool_display_name: z.string(),
  args: z.record(z.unknown()),
  status: z.string(),
  result: z.unknown().nullable().optional(),
  error: z.string().nullable().optional(),
  duration_ms: z.number().nullable().optional(),
});

export const JobStatusResponseSchema = z.object({
  status: z.enum(["running", "completed", "awaiting_confirmation", "failed"]),
  result: z.record(z.unknown()).nullable().optional(),
  tool_executions: z.array(z.record(z.unknown())).nullable().optional(),
  error: z.string().nullable().optional(),
  confirmation: z.record(z.unknown()).nullable().optional(),
});

export const ProcessingJobResponseSchema = z.object({
  id: z.string(),
  status: z.string(),
  progress_percentage: z.number().optional(),
  current_step: z.string().nullable().optional(),
  total_steps: z.number().nullable().optional(),
  error_message: z.string().nullable().optional(),
  duration_seconds: z.number().nullable().optional(),
});

export const AgentExecutePayloadSchema = z.object({
  messages: z.array(z.object({ role: z.string(), content: z.string() })),
  pageContext: z.object({
    type: z.string(),
    project_id: z.string().optional(),
    metadata: z.record(z.unknown()).optional(),
  }),
  model: z.string().optional(),
  useRag: z.boolean().optional(),
  maxContextDocs: z.number().optional(),
  threadId: z.string().optional(),
  userId: z.string(),
  accessToken: z.string(),
});

export const ArxivBulkIngestPayloadSchema = z.object({
  query: z.string(),
  maxResults: z.number().min(1).max(1000).default(100),
  categories: z.array(z.string()).optional(),
  dateFrom: z.string().optional(),
  dateTo: z.string().optional(),
  batchSize: z.number().min(1).max(50).default(10),
  userId: z.string(),
});

export const ArxivIngestPaperPayloadSchema = z.object({
  paperId: z.string(),
  downloadPdf: z.boolean().default(true),
  userId: z.string(),
});

export const ArxivSearchResponseSchema = z.object({
  papers: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      authors: z.array(z.string()).optional(),
      categories: z.array(z.string()).optional(),
      published: z.string().optional(),
    }),
  ),
  total: z.number().optional(),
});

export const BatchProcessPayloadSchema = z.object({
  documentIds: z.array(z.string()).min(1).max(100),
  priority: z.enum(["low", "normal", "high"]).default("normal"),
  userId: z.string(),
});

export const CacheWarmPayloadSchema = z.object({
  documentId: z.string(),
  documentTitle: z.string().optional(),
});

export type HealthCheckResponse = z.infer<typeof HealthCheckResponseSchema>;
export type JobStartResponse = z.infer<typeof JobStartResponseSchema>;
export type JobStatusResponse = z.infer<typeof JobStatusResponseSchema>;
export type ProcessingJobResponse = z.infer<typeof ProcessingJobResponseSchema>;
export type ToolExecution = z.infer<typeof ToolExecutionSchema>;
export type AgentExecutePayload = z.infer<typeof AgentExecutePayloadSchema>;
export type ArxivBulkIngestPayload = z.infer<
  typeof ArxivBulkIngestPayloadSchema
>;
export type ArxivIngestPaperPayload = z.infer<
  typeof ArxivIngestPaperPayloadSchema
>;
export type BatchProcessPayload = z.infer<typeof BatchProcessPayloadSchema>;
export type CacheWarmPayload = z.infer<typeof CacheWarmPayloadSchema>;
