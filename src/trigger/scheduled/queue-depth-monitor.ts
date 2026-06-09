import { logger, schedules } from "@trigger.dev/sdk";
import { backendClient } from "../_lib/backend-client";

const SLACK_WEBHOOK_URL = process.env.SLACK_DIGEST_WEBHOOK_URL;
const PENDING_THRESHOLD = 50;

async function sendSlackAlert(text: string): Promise<void> {
  if (!SLACK_WEBHOOK_URL) {
    logger.warn("SLACK_DIGEST_WEBHOOK_URL not set, skipping alert");
    return;
  }

  const res = await fetch(SLACK_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      blocks: [
        {
          type: "section",
          text: { type: "mrkdwn", text },
        },
      ],
    }),
  });

  if (!res.ok) {
    logger.error("Slack alert failed", { status: res.status });
  }
}

export const queueDepthMonitor = schedules.task({
  id: "queue-depth-monitor",
  cron: "*/5 * * * *",
  run: async () => {
    logger.info("Checking queue depth");

    let workerCount = 0;
    let pendingTasks = 0;

    try {
      const status = await backendClient.get<{
        workers?: Array<Record<string, unknown>>;
        pending_tasks?: number;
        active_tasks?: number;
      }>("/api/v1/infrastructure/workers/status");

      workerCount = status.workers?.length ?? 0;
      pendingTasks = status.pending_tasks ?? 0;

      logger.info("Queue depth check", {
        workerCount,
        pendingTasks,
        activeTasks: status.active_tasks ?? 0,
      });
    } catch (err) {
      logger.error("Failed to fetch worker status", { error: String(err) });
      await sendSlackAlert(
        `:warning: *NOUS Queue Monitor* — Failed to reach worker status endpoint: ${String(err)}`,
      );
      return { status: "error", error: String(err) };
    }

    const alerts: string[] = [];

    if (workerCount === 0) {
      alerts.push(":rotating_light: *No active workers detected*");
    }

    if (pendingTasks > PENDING_THRESHOLD) {
      alerts.push(
        `:warning: *Queue depth high:* ${pendingTasks} pending tasks (threshold: ${PENDING_THRESHOLD})`,
      );
    }

    if (alerts.length > 0) {
      await sendSlackAlert(
        `*NOUS Queue Alert*\n${alerts.join("\n")}\n\nWorkers: ${workerCount} | Pending: ${pendingTasks}`,
      );
      logger.warn("Queue alerts triggered", { alerts });
    }

    return {
      status: alerts.length > 0 ? "alerted" : "ok",
      workerCount,
      pendingTasks,
      alerts,
    };
  },
});
