import { logger, task, wait, metadata } from "@trigger.dev/sdk";
import { backendClient, BackendApiError } from "../_lib/backend-client";
import {
  JobStartResponseSchema,
  JobStatusResponseSchema,
  type AgentExecutePayload,
  type JobStatusResponse,
} from "../_lib/schemas";

const MAX_POLL_ATTEMPTS = 120;
const POLL_INTERVAL_SECONDS = 3;

function userAuth(accessToken: string): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` };
}

async function pollUntilDone(
  jobId: string,
  accessToken: string,
  userId: string,
): Promise<{ status: string; result?: Record<string, unknown> }> {
  for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
    let job: JobStatusResponse;
    try {
      job = await backendClient.get(
        `/api/v1/agent/jobs/${jobId}`,
        JobStatusResponseSchema,
        userAuth(accessToken),
      );
    } catch (err) {
      if (err instanceof BackendApiError && err.status === 404) {
        logger.error("Agent job not found", { jobId });
        return { status: "not_found" };
      }
      throw err;
    }

    metadata.set("backendStatus", job.status);

    if (job.status === "completed") {
      return { status: "completed", result: job.result ?? undefined };
    }

    if (job.status === "failed") {
      return { status: "failed", result: { error: job.error } };
    }

    if (job.status === "awaiting_confirmation" && job.confirmation) {
      metadata.set("status", "awaiting_confirmation");
      metadata.set(
        "confirmation",
        JSON.parse(JSON.stringify(job.confirmation)),
      );

      const token = await wait.createToken({
        idempotencyKey: `hitl-${jobId}-${Date.now()}`,
        timeout: "1h",
        tags: [`user:${userId}`, `job:${jobId}`],
      });
      metadata.set("waitTokenId", token.id);

      const decision = await wait
        .forToken<{ confirmed: boolean }>(token)
        .unwrap();

      metadata.set("status", "running");
      metadata.del("confirmation");
      metadata.del("waitTokenId");

      await backendClient.post(
        `/api/v1/agent/confirm/${jobId}`,
        { confirmed: decision.confirmed },
        undefined,
        userAuth(accessToken),
      );

      continue;
    }

    await wait.for({ seconds: POLL_INTERVAL_SECONDS });
  }

  return { status: "timeout" };
}

export const executeAgent = task({
  id: "execute-agent",
  maxDuration: 600,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 30000,
    factor: 2,
  },
  run: async (payload: AgentExecutePayload) => {
    const { accessToken, userId, ...requestFields } = payload;

    logger.info("Starting durable agent execution", { userId });
    metadata.set("status", "running");
    metadata.set("userId", userId);

    const backendRequest = {
      messages: requestFields.messages,
      page_context: requestFields.pageContext,
      model: requestFields.model ?? "",
      use_rag: requestFields.useRag ?? true,
      max_context_docs: requestFields.maxContextDocs ?? 5,
      thread_id: requestFields.threadId,
    };

    const { job_id } = await backendClient.post(
      "/api/v1/agent/execute",
      backendRequest,
      JobStartResponseSchema,
      userAuth(accessToken),
    );

    metadata.set("backendJobId", job_id);
    logger.info("Backend job created", { jobId: job_id });

    const result = await pollUntilDone(job_id, accessToken, userId);

    metadata.set("status", result.status);
    logger.info("Agent execution finished", {
      jobId: job_id,
      status: result.status,
    });

    return result;
  },
});
