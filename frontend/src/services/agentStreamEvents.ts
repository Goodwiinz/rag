/**
 * Agent SSE event vocabulary — the single frontend mirror of the backend
 * `AgentStreamEvent` StrEnum (backend/src/shared/enums.py).
 *
 * These values ARE the SSE wire contract: they must stay byte-identical to the
 * backend enum's values. This is the ONE place the frontend enumerates the
 * event names — the consumer switch in `agentChatService.ts` dispatches on
 * them, and `agentStreamEvents.contract.test.ts` fails CI if the switch (or its
 * exported `HANDLED_STREAM_EVENTS` set) drifts from this list. Keep this list in
 * lockstep with the backend enum by hand; a mismatch surfaces as a dropped or
 * unhandled event, so both the backend and frontend contract tests guard it.
 */
export const AGENT_STREAM_EVENTS = [
  'token',
  'tool_start',
  'tool_end',
  'rag_context',
  'plan',
  'reflection',
  'trace',
  'usage',
  'heartbeat',
  'confirmation',
  'done',
  'error',
] as const;

/** Union of every agent SSE event name (mirror of backend `AgentStreamEvent`). */
export type AgentStreamEvent = (typeof AGENT_STREAM_EVENTS)[number];

/**
 * `heartbeat` is the keepalive the backend emits during silent planner/LLM
 * phases. It carries `elapsed_ms`, which the consumer surfaces as live
 * progress on the thinking pill — like every other event, it is handled.
 */
export const HEARTBEAT_STREAM_EVENT = 'heartbeat' satisfies AgentStreamEvent;

/**
 * Terminal frames — the live stream (and the resumable replay) ends after one
 * of these. Mirror of backend `TERMINAL_STREAM_EVENTS`.
 */
export const TERMINAL_STREAM_EVENTS: ReadonlySet<AgentStreamEvent> = new Set([
  'done',
  'error',
  'confirmation',
]);
