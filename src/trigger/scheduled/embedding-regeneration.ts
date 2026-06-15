import { logger, schedules, metadata } from "@trigger.dev/sdk";
import { backendClient } from "../_lib/backend-client";

const LAST_MODEL_VERSION_KEY = "lastEmbeddingModelVersion";

export const embeddingRegeneration = schedules.task({
  id: "embedding-regeneration",
  cron: "0 2 * * 0",
  run: async () => {
    logger.info("Checking embedding model version");
    metadata.set("status", "checking");

    let currentModel: string;
    try {
      const info = await backendClient.get<{
        model_name?: string;
        model_version?: string;
      }>("/api/v1/search/vectors/model-info");
      currentModel =
        `${info.model_name ?? "unknown"}:${info.model_version ?? "unknown"}`;
    } catch (err) {
      logger.error("Failed to fetch model info", { error: String(err) });
      return { status: "error", error: String(err) };
    }

    metadata.set("currentModel", currentModel);

    const lastKnown = process.env[LAST_MODEL_VERSION_KEY] ?? "";

    if (lastKnown && lastKnown === currentModel) {
      logger.info("Embedding model unchanged, skipping regeneration", {
        model: currentModel,
      });
      return { status: "skipped", model: currentModel };
    }

    if (!lastKnown) {
      logger.info(
        "No previous model version recorded, storing current and skipping",
        { model: currentModel },
      );
      return {
        status: "baseline_set",
        model: currentModel,
        note: `Set ${LAST_MODEL_VERSION_KEY}=${currentModel} in Trigger.dev env vars`,
      };
    }

    logger.info("Embedding model changed, triggering regeneration", {
      previous: lastKnown,
      current: currentModel,
    });
    metadata.set("status", "regenerating");

    try {
      const result = await backendClient.post<{ job_id?: string }>(
        "/api/v1/search/vectors/regenerate",
        { reason: `Model changed: ${lastKnown} → ${currentModel}` },
      );

      logger.info("Regeneration triggered", { jobId: result.job_id });
      metadata.set("status", "triggered");

      return {
        status: "regeneration_triggered",
        previousModel: lastKnown,
        currentModel,
        jobId: result.job_id,
      };
    } catch (err) {
      logger.error("Failed to trigger regeneration", { error: String(err) });
      return {
        status: "error",
        previousModel: lastKnown,
        currentModel,
        error: String(err),
      };
    }
  },
});
