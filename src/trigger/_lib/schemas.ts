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

export type HealthCheckResponse = z.infer<typeof HealthCheckResponseSchema>;
export type JobStartResponse = z.infer<typeof JobStartResponseSchema>;
export type JobStatusResponse = z.infer<typeof JobStatusResponseSchema>;
export type ProcessingJobResponse = z.infer<typeof ProcessingJobResponseSchema>;
export type ToolExecution = z.infer<typeof ToolExecutionSchema>;
