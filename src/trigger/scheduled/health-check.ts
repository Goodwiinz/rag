import { logger, schedules } from "@trigger.dev/sdk";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import { HealthCheckResponseSchema } from "../_lib/schemas";

export const systemHealthMonitor = schedules.task({
  id: "system-health-monitor",
  cron: "*/15 * * * *",
  run: async () => {
    logger.info("Running system health check");

    const results: Record<string, unknown> = {};

    try {
      const health = await backendClient.get(
        "/health",
        HealthCheckResponseSchema,
      );
      results.backend = { status: "healthy", detail: health };
    } catch (err) {
      const message =
        err instanceof BackendApiError ? `HTTP ${err.status}` : String(err);
      results.backend = { status: "unhealthy", error: message };
      logger.error("Backend health check failed", { error: message });
    }

    try {
      const workers = await backendClient.get(
        "/api/v1/infrastructure/workers/health",
      );
      results.workers = { status: "healthy", detail: workers };
    } catch (err) {
      const message =
        err instanceof BackendApiError ? `HTTP ${err.status}` : String(err);
      results.workers = { status: "unknown", error: message };
      logger.warn("Worker health check unavailable", { error: message });
    }

    const allHealthy = Object.values(results).every(
      (r) => (r as Record<string, unknown>).status === "healthy",
    );

    logger.info("Health check completed", {
      overall: allHealthy ? "healthy" : "degraded",
      results,
    });

    return {
      overall: allHealthy ? "healthy" : "degraded",
      timestamp: new Date().toISOString(),
      results,
    };
  },
});
