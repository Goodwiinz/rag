import { logger, task, wait } from "@trigger.dev/sdk";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import type { ArxivIngestPaperPayload } from "../_lib/schemas";

const MAX_POLL_ATTEMPTS = 60;
const POLL_INTERVAL_SECONDS = 10;

export const ingestPaper = task({
  id: "arxiv-ingest-paper",
  maxDuration: 300,
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 10000,
    maxTimeoutInMs: 60000,
    factor: 3,
  },
  run: async (payload: ArxivIngestPaperPayload) => {
    const { paperId } = payload;

    logger.info("Ingesting ArXiv paper", { paperId });

    let result: Record<string, unknown>;
    try {
      result = await backendClient.post<Record<string, unknown>>(
        "/api/v1/arxiv/ingest",
        { paper_ids: [paperId] },
      );
    } catch (err) {
      if (err instanceof BackendApiError && err.status === 429) {
        logger.warn("Rate limited by ArXiv, will retry", { paperId });
        throw err;
      }
      throw err;
    }

    const documentIds = (result.document_ids as string[]) ?? [];
    if (documentIds.length === 0) {
      logger.info("Paper already ingested or skipped", { paperId });
      return { status: "skipped", paperId };
    }

    logger.info("Paper ingested, polling for processing", {
      paperId,
      documentIds,
    });

    for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
      await wait.for({ seconds: POLL_INTERVAL_SECONDS });

      try {
        const job = await backendClient.get<Record<string, unknown>>(
          `/api/v1/processing/jobs/${documentIds[0]}`,
        );
        if (job.status === "completed") {
          return { status: "completed", paperId, documentIds };
        }
        if (job.status === "failed") {
          return { status: "failed", paperId, error: job.error_message };
        }
      } catch (err) {
        if (err instanceof BackendApiError && err.status === 404) {
          return { status: "completed", paperId, documentIds };
        }
        throw err;
      }
    }

    return { status: "timeout", paperId };
  },
});
