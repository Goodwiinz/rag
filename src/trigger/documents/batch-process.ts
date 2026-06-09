import { logger, task, metadata } from "@trigger.dev/sdk";
import { orchestrateDocumentProcessing } from "./process-document";
import { backendClient } from "../_lib/backend-client";
import type { BatchProcessPayload } from "../_lib/schemas";

export const batchProcessDocuments = task({
  id: "batch-process-documents",
  maxDuration: 3600,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 30000,
    factor: 2,
  },
  run: async (payload: BatchProcessPayload) => {
    const { documentIds, priority } = payload;

    logger.info("Starting batch document processing", {
      count: documentIds.length,
      priority,
    });
    metadata.set("status", "creating_jobs");
    metadata.set("totalDocuments", documentIds.length);

    const jobs: Array<{ jobId: string; documentId: string }> = [];
    const errors: Array<{ documentId: string; error: string }> = [];

    for (const documentId of documentIds) {
      try {
        const result = await backendClient.post<{ job_id: string }>(
          "/api/v1/processing/documents/process",
          { document_id: documentId, priority },
        );
        jobs.push({ jobId: result.job_id, documentId });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        errors.push({ documentId, error: message });
        logger.warn("Failed to create processing job", {
          documentId,
          error: message,
        });
      }
    }

    if (jobs.length === 0) {
      metadata.set("status", "failed");
      return { status: "failed", completed: 0, failed: errors.length, errors };
    }

    metadata.set("status", "processing");
    metadata.set("jobsCreated", jobs.length);

    const results = await orchestrateDocumentProcessing.batchTriggerAndWait(
      jobs.map(({ jobId, documentId }) => ({
        payload: { jobId, documentId },
      })),
    );

    let completed = 0;
    let failed = 0;
    for (const run of results.runs) {
      if (run.ok && run.output?.status === "completed") {
        completed++;
      } else {
        failed++;
      }
    }

    metadata.set("status", "completed");
    metadata.set("progress", 1);

    logger.info("Batch processing complete", {
      completed,
      failed,
      errors: errors.length,
    });

    return {
      status: "completed",
      completed,
      failed,
      errors,
      total: documentIds.length,
    };
  },
});
