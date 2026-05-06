import { logger, task } from "@trigger.dev/sdk/v3";
import { backendClient } from "../_lib/backend-client";
import type { CacheWarmPayload } from "../_lib/schemas";

export const cacheWarmAfterProcessing = task({
  id: "cache-warm-after-processing",
  maxDuration: 300,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 2000,
    maxTimeoutInMs: 10000,
    factor: 2,
  },
  run: async (payload: CacheWarmPayload) => {
    const { documentId, documentTitle } = payload;

    logger.info("Warming cache for processed document", { documentId });

    const query = documentTitle || documentId;

    try {
      await backendClient.post("/api/v1/search", {
        query,
        limit: 5,
        document_ids: [documentId],
      });
      logger.info("Cache warmed via search", { documentId });
    } catch (err) {
      logger.warn("Cache warm search failed, non-fatal", {
        documentId,
        error: String(err),
      });
    }

    return { status: "completed", documentId };
  },
});
