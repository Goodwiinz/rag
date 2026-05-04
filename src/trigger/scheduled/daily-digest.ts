import { logger, schedules } from "@trigger.dev/sdk/v3";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import { HealthCheckResponseSchema } from "../_lib/schemas";

const SLACK_WEBHOOK_URL = process.env.SLACK_DIGEST_WEBHOOK_URL;

async function sendSlackMessage(blocks: unknown[]): Promise<void> {
  if (!SLACK_WEBHOOK_URL) {
    logger.warn("SLACK_DIGEST_WEBHOOK_URL not set, skipping Slack notification");
    return;
  }

  const res = await fetch(SLACK_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ blocks }),
  });

  if (!res.ok) {
    logger.error("Slack webhook failed", { status: res.status });
  }
}

export const dailyDigest = schedules.task({
  id: "daily-digest",
  cron: "0 8 * * *",
  run: async () => {
    logger.info("Generating daily digest");

    let backendStatus = "unknown";
    let backendVersion = "";
    try {
      const health = await backendClient.get(
        "/health",
        HealthCheckResponseSchema,
      );
      backendStatus = health.status;
      backendVersion = health.version ?? "";
    } catch (err) {
      const message =
        err instanceof BackendApiError ? `HTTP ${err.status}` : String(err);
      backendStatus = `unhealthy: ${message}`;
    }

    let workerCount = 0;
    let pendingTasks = 0;
    try {
      const workers = await backendClient.get<{
        workers?: Array<Record<string, unknown>>;
        pending_tasks?: number;
      }>("/api/v1/infrastructure/workers/health");
      workerCount = workers.workers?.length ?? 0;
      pendingTasks = workers.pending_tasks ?? 0;
    } catch {
      logger.warn("Worker health unavailable for digest");
    }

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);

    const blocks = [
      {
        type: "header",
        text: {
          type: "plain_text",
          text: `NOUS Daily Digest — ${dateStr}`,
        },
      },
      {
        type: "section",
        fields: [
          {
            type: "mrkdwn",
            text: `*Backend:* ${backendStatus}${backendVersion ? ` (v${backendVersion})` : ""}`,
          },
          { type: "mrkdwn", text: `*Workers:* ${workerCount} active` },
          { type: "mrkdwn", text: `*Pending Tasks:* ${pendingTasks}` },
        ],
      },
    ];

    await sendSlackMessage(blocks);

    logger.info("Daily digest sent", {
      backendStatus,
      workerCount,
      pendingTasks,
    });

    return {
      date: dateStr,
      backendStatus,
      workerCount,
      pendingTasks,
    };
  },
});
