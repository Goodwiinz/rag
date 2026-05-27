import { logger, task, metadata } from "@trigger.dev/sdk/v3";
import { ingestPaper } from "./ingest-paper";
import { backendClient } from "../_lib/backend-client";
import type { ArxivBulkIngestPayload } from "../_lib/schemas";

export const bulkIngestArxiv = task({
  id: "arxiv-bulk-ingest",
  maxDuration: 3600,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 10000,
    maxTimeoutInMs: 60000,
    factor: 2,
  },
  run: async (payload: ArxivBulkIngestPayload) => {
    const {
      query,
      maxResults,
      categories,
      dateFrom,
      dateTo,
      batchSize,
      userId,
    } = payload;

    logger.info("Starting ArXiv bulk ingestion", { query, maxResults });
    metadata.set("status", "searching");

    const searchParams: Record<string, unknown> = {
      query,
      max_results: maxResults,
    };
    if (categories) searchParams.categories = categories;
    if (dateFrom) searchParams.date_from = dateFrom;
    if (dateTo) searchParams.date_to = dateTo;

    const searchResult = await backendClient.post<{
      papers: Array<{ id: string; title: string }>;
      total?: number;
    }>("/api/v1/arxiv/search", searchParams);

    const papers = searchResult.papers ?? [];
    metadata.set("totalPapers", papers.length);
    metadata.set("status", "ingesting");

    if (papers.length === 0) {
      logger.info("No papers found for query", { query });
      return { status: "completed", ingested: 0, failed: 0, total: 0 };
    }

    const batches: Array<Array<{ id: string; title: string }>> = [];
    for (let i = 0; i < papers.length; i += batchSize) {
      batches.push(papers.slice(i, i + batchSize));
    }

    let ingested = 0;
    let failed = 0;

    for (let batchIdx = 0; batchIdx < batches.length; batchIdx++) {
      const batch = batches[batchIdx];

      const results = await ingestPaper.batchTriggerAndWait(
        batch.map((paper) => ({
          payload: { paperId: paper.id, downloadPdf: true, userId },
        })),
      );

      for (const run of results.runs) {
        if (run.ok) {
          ingested++;
        } else {
          failed++;
        }
      }

      metadata.set("progress", (batchIdx + 1) / batches.length);
      metadata.set("ingested", ingested);
      metadata.set("failed", failed);

      logger.info("Batch complete", {
        batch: batchIdx + 1,
        total: batches.length,
        ingested,
        failed,
      });
    }

    metadata.set("status", "completed");
    return { status: "completed", ingested, failed, total: papers.length };
  },
});
