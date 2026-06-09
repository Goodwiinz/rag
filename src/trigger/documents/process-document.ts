import { logger, task, wait } from "@trigger.dev/sdk";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import { cacheWarmAfterProcessing } from "./cache-warm";
import {
  ProcessingJobResponseSchema,
  type ProcessingJobResponse,
} from "../_lib/schemas";

const MAX_POLL_ATTEMPTS = 360;
const POLL_INTERVAL_SECONDS = 5;

export const orchestrateDocumentProcessing = task({
  id: "orchestrate-document-processing",
  maxDuration: 3600,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 30000,
    factor: 2,
  },
  run: async (payload: { jobId: string; documentId: string }) => {
    const { jobId, documentId } = payload;

    logger.info("Starting document processing orchestration", {
      jobId,
      documentId,
    });

    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
      let job: ProcessingJobResponse;
      try {
        job = await backendClient.get(
          `/api/v1/processing/jobs/${jobId}`,
          ProcessingJobResponseSchema,
        );
      } catch (err) {
        if (err instanceof BackendApiError && err.status === 404) {
          logger.error("Processing job not found", { jobId });
          return { status: "not_found", jobId };
        }
        throw err;
      }

      logger.info("Polling processing status", {
        jobId,
        status: job.status,
        progress: job.progress_percentage,
        step: job.current_step,
      });

      if (job.status === "completed") {
        logger.info("Document processing completed", { jobId, documentId });

        await cacheWarmAfterProcessing.trigger({
          documentId,
          documentTitle: undefined,
        });

        return {
          status: "completed",
          jobId,
          documentId,
          duration: job.duration_seconds,
        };
      }

      if (job.status === "failed") {
        logger.error("Document processing failed", {
          jobId,
          error: job.error_message,
        });
        return {
          status: "failed",
          jobId,
          documentId,
          error: job.error_message,
        };
      }

      await wait.for({ seconds: POLL_INTERVAL_SECONDS });
    }

    logger.warn("Document processing timed out after polling", {
      jobId,
      maxAttempts: MAX_POLL_ATTEMPTS,
    });
    return { status: "timeout", jobId, documentId };
  },
});
