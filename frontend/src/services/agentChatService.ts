import { api } from '@/services/api-client';
import { createClient } from '@/lib/supabase/client';
import { getPublicApiBaseUrl } from '@/utils/publicEndpoints';
import { parseErrorBody } from '@/utils/parseErrorBody';

function agentStreamUrl(path: 'stream' | 'stream/confirm'): string {
  const base = getPublicApiBaseUrl('/api/v1').replace(/\/$/, '');
  return `${base}/agent/${path}`;
}

async function getStreamAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      headers['Authorization'] = `Bearer ${session.access_token}`;
    }
    const orgId = session?.user?.user_metadata?.organization_id;
    if (orgId) {
      headers['X-Organization-ID'] = orgId;
    }
  } catch {
    // Fall through without auth headers
  }
  return headers;
}

/**
 * Callbacks shared by all agent SSE consumers (streamMessage, streamConfirm,
 * resumeStream). One superset shape — individual streams simply never emit
 * some events (e.g. streamConfirm never emits trace).
 */
export interface AgentStreamCallbacks {
  onToken?: (content: string) => void;
  onToolStart?: (tool: string, args: Record<string, unknown>) => void;
  onToolEnd?: (tool: string, result: string, isError: boolean) => void;
  onRagContext?: (contexts: Array<Record<string, unknown>>) => void;
  onPlan?: (steps: Array<Record<string, unknown>>, reasoning: string) => void;
  onReflection?: (
    passed: boolean,
    issues: string[],
    round: number,
    revising?: boolean
  ) => void;
  onConfirmation?: (
    threadId: string,
    confirmation: Record<string, unknown>
  ) => void;
  onTrace?: (threadId: string) => void;
  onUsage?: (inputTokens: number, outputTokens: number) => void;
  /** Fires for every frame carrying an `id: <seq>` line — the resumable-SSE
   * cursor. Persist the latest value to resume after a disconnect. */
  onSeq?: (seq: number) => void;
  onDone?: (payload?: {
    thread_id?: string;
    assistant_message_id?: string | null;
    client_message_id?: string | null;
    /** Full-fidelity tool executions from the graph state (parsed
     * results, real durations) — richer than the live SSE summaries. */
    tool_executions?: Array<Record<string, unknown>>;
  }) => void;
  onError?: (error: string) => void;
}

/** Read the backend's error body so the user sees the real cause, not just
 * an HTTP number. The backend returns the structured envelope
 * `{ error: { message, ... } }`; older paths may return `{detail: "..."}`. */
async function readErrorBody(response: Response): Promise<string> {
  let backendMessage = '';
  try {
    const text = await response.text();
    if (text) {
      try {
        const parsed = parseErrorBody(JSON.parse(text));
        backendMessage =
          parsed.message === 'Request failed'
            ? text.slice(0, 500)
            : parsed.message;
      } catch {
        backendMessage = text.slice(0, 500);
      }
    }
  } catch {
    // Ignore — fall back to status code only.
  }
  return backendMessage;
}

/**
 * Shared SSE consume loop: reads `response.body`, parses `id:`/`event:`/
 * `data:` lines (chunk-boundary and CRLF safe), and dispatches to callbacks.
 * AbortError is swallowed — an aborted stream resolves quietly.
 */
async function consumeSse(
  response: Response,
  callbacks: AgentStreamCallbacks
): Promise<void> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let eventType = '';

  const dispatchData = (ev: string, dataLine: string): void => {
    try {
      const data = JSON.parse(dataLine.slice(6));
      switch (ev) {
        case 'token':
          callbacks.onToken?.(data.content);
          break;
        case 'tool_start':
          callbacks.onToolStart?.(data.tool, data.args);
          break;
        case 'tool_end':
          callbacks.onToolEnd?.(data.tool, data.result, Boolean(data.is_error));
          break;
        case 'rag_context':
          callbacks.onRagContext?.(data.contexts);
          break;
        case 'plan':
          callbacks.onPlan?.(data.steps, data.reasoning ?? '');
          break;
        case 'trace':
          if (data.thread_id) {
            callbacks.onTrace?.(data.thread_id);
          }
          break;
        case 'reflection':
          callbacks.onReflection?.(
            data.passed,
            data.issues,
            data.round,
            data.revising
          );
          break;
        case 'confirmation':
          callbacks.onConfirmation?.(data.thread_id, data.confirmation);
          break;
        case 'usage':
          callbacks.onUsage?.(
            Number(data.input_tokens) || 0,
            Number(data.output_tokens) || 0
          );
          break;
        case 'done':
          // Server-canonical persistence: the done payload carries the
          // persisted ids so the client can reconcile its optimistic
          // bubbles instead of double-saving. Legacy servers send only
          // {status} — the payload fields are simply undefined then.
          callbacks.onDone?.(data);
          break;
        case 'error':
          callbacks.onError?.(
            typeof data.error === 'string'
              ? data.error
              : String(data.error?.message || JSON.stringify(data.error))
          );
          break;
      }
    } catch (err) {
      console.warn('[Chat] Malformed SSE data line, skipping:', dataLine, err);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
          eventType = '';
          continue;
        }
        if (line.startsWith('id: ')) {
          const seq = parseInt(line.slice(4), 10);
          if (!Number.isNaN(seq)) callbacks.onSeq?.(seq);
        } else if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ') && eventType) {
          dispatchData(eventType, line);
        }
      }
    }
    // Defensive flush: if the server's final chunk ended without a
    // trailing \n (the backend always \n\n-terminates, so this is
    // rare), buffer holds an unprocessed data: line — process it so
    // the last event isn't silently dropped.
    if (buffer.trim() && eventType) {
      const tail = buffer.trim();
      if (tail.startsWith('data: ')) {
        dispatchData(eventType, tail);
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return;
    throw err;
  } finally {
    reader.releaseLock();
  }
}

export interface AgentExecuteRequest {
  messages: Array<{
    role: string;
    content: string;
    /** Idempotency key for the user turn (server-canonical persistence). */
    client_message_id?: string;
  }>;
  page_context: {
    type: string;
    project_id?: string;
    metadata?: Record<string, unknown>;
  };
  model?: string;
  use_rag?: boolean;
  max_context_docs?: number;
  thread_id?: string;
}

export interface AgentExecuteResponse {
  message: {
    role: string;
    content: string;
  };
  model: string;
  usage: Record<string, number>;
  finish_reason: string;
  timestamp: string;
  rag_enabled: boolean;
  retrieved_contexts?: Array<{
    document_id?: string;
    title: string;
    content: string;
    score: number;
  }>;
  tool_executions?: Array<{
    id: string;
    tool_name: string;
    tool_display_name: string;
    args: Record<string, unknown>;
    status: string;
    result?: unknown;
    error?: string;
    duration_ms?: number;
  }>;
  thread_id: string;
  conversation_id: string;
}

export interface ThreadListResponse {
  threads: Array<{
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message_at?: string;
    source_project_id?: string;
  }>;
  total: number;
}

export interface ThreadMessagesResponse {
  messages: Array<{
    id: string;
    role: string;
    content: string;
    created_at: string;
    tool_name?: string;
    tool_call_id?: string;
    citations?: Array<{
      document_id: string;
      document_title: string;
      snippet?: string;
      page_number?: number;
      score?: number;
    }>;
    tool_executions?: Array<{
      id: string;
      tool_name: string;
      tool_display_name: string;
      args: Record<string, unknown>;
      status: string;
      result?: unknown;
      error?: string;
      duration_ms?: number;
    }>;
  }>;
  total: number;
}

/**
 * Agent job lifecycle status — mirror of backend `JobStatus`
 * (backend/src/shared/enums.py).
 *
 * 'error' is the legacy alias for 'failed': the backend collapsed the split
 * and normalizes it away on read, but a not-yet-redeployed backend (or a
 * record written before the collapse) can still return it for one release.
 * Treat it exactly like 'failed'.
 */
export type AgentJobStatus =
  | 'running'
  | 'awaiting_confirmation'
  | 'completed'
  | 'failed'
  | 'error'
  | 'cancelled';

/**
 * True when the job can never transition again — the poller must stop.
 *
 * Exhaustive over AgentJobStatus: adding a status without classifying it
 * here is a compile error (`never` check in the default arm). Previously the
 * poller hand-listed 'completed'/'failed' and spun for the full poll budget
 * on 'error' and 'cancelled' jobs (audit C7).
 */
export function isTerminalJobStatus(status: AgentJobStatus): boolean {
  switch (status) {
    case 'completed':
    case 'failed':
    case 'error':
    case 'cancelled':
      return true;
    case 'running':
    case 'awaiting_confirmation':
      return false;
    default: {
      // Compile-time exhaustiveness; at runtime an unknown status (from a
      // newer backend) keeps polling until the caller's poll budget runs out.
      const _exhaustive: never = status;
      void _exhaustive;
      return false;
    }
  }
}

class AgentChatService {
  async startJob(request: AgentExecuteRequest): Promise<{ job_id: string }> {
    return api.post<{ job_id: string }>('/agent/execute', request);
  }

  async pollJob(jobId: string): Promise<{
    status: AgentJobStatus;
    result?: AgentExecuteResponse;
    tool_executions?: Array<{
      id: string;
      tool_name: string;
      tool_display_name: string;
      args: Record<string, unknown>;
      status: string;
      result?: unknown;
      error?: string;
      duration_ms?: number;
    }>;
    error?: string;
    confirmation?: {
      tools?: Array<{ name: string; args: Record<string, unknown> }>;
      message?: string;
    };
  }> {
    return api.get(`/agent/jobs/${encodeURIComponent(jobId)}`);
  }

  async confirmAction(
    jobId: string,
    confirmed: boolean
  ): Promise<{ status: string; job_id: string }> {
    return api.post(`/agent/confirm/${encodeURIComponent(jobId)}`, {
      confirmed,
    });
  }

  async streamMessage(
    request: AgentExecuteRequest,
    callbacks: AgentStreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const headers = await getStreamAuthHeaders();

    let response: Response;
    try {
      response = await fetch(agentStreamUrl('stream'), {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      throw err;
    }

    if (!response.ok || !response.body) {
      const backendMessage = await readErrorBody(response);
      callbacks.onError?.(
        backendMessage
          ? `Stream failed (${response.status}): ${backendMessage}`
          : `Stream failed: ${response.status}`
      );
      return;
    }

    await consumeSse(response, callbacks);
  }

  /**
   * Resume an in-flight (or just-finished, still-buffered) agent stream.
   * 204 means nothing is active for the thread — a clean no-op. Otherwise
   * the buffered frames after `afterSeq` replay through the same callbacks
   * as streamMessage, ending with the terminal frame (done/error/
   * confirmation).
   */
  async resumeStream(
    threadId: string,
    afterSeq: number,
    callbacks: AgentStreamCallbacks,
    signal?: AbortSignal
  ): Promise<{ resumed: boolean }> {
    const base = getPublicApiBaseUrl('/api/v1').replace(/\/$/, '');
    const url = `${base}/agent/stream/resume/${encodeURIComponent(
      threadId
    )}?after=${afterSeq}`;
    const headers = await getStreamAuthHeaders();

    let response: Response;
    try {
      response = await fetch(url, { method: 'GET', headers, signal });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return { resumed: false };
      }
      throw err;
    }

    if (response.status === 204) {
      return { resumed: false };
    }
    if (!response.ok || !response.body) {
      const backendMessage = await readErrorBody(response);
      callbacks.onError?.(
        backendMessage
          ? `Stream resume failed (${response.status}): ${backendMessage}`
          : `Stream resume failed: ${response.status}`
      );
      return { resumed: false };
    }

    await consumeSse(response, callbacks);
    return { resumed: true };
  }

  async streamConfirm(
    request: { thread_id: string; confirmed: boolean },
    callbacks: AgentStreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const headers = await getStreamAuthHeaders();

    let response: Response;
    try {
      response = await fetch(agentStreamUrl('stream/confirm'), {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      throw err;
    }

    if (!response.ok || !response.body) {
      const backendMessage = await readErrorBody(response);
      callbacks.onError?.(
        backendMessage
          ? `Stream confirm failed (${response.status}): ${backendMessage}`
          : `Stream confirm failed: ${response.status}`
      );
      return;
    }

    await consumeSse(response, callbacks);
  }
  async startDurableRun(
    request: AgentExecuteRequest
  ): Promise<{ runId: string }> {
    const res = await fetch('/api/trigger/agent/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Failed to start durable run: ${text}`);
    }
    return res.json();
  }

  async getDurableRunStatus(runId: string): Promise<{
    runId: string;
    status: string;
    metadata: Record<string, unknown>;
    output: Record<string, unknown> | null;
    error: string | null;
  }> {
    const res = await fetch(
      `/api/trigger/agent/runs/${encodeURIComponent(runId)}`
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Failed to get run status: ${text}`);
    }
    return res.json();
  }

  async completeDurableConfirmation(
    runId: string,
    tokenId: string,
    confirmed: boolean
  ): Promise<void> {
    const res = await fetch(
      `/api/trigger/agent/runs/${encodeURIComponent(runId)}/confirm`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tokenId, confirmed }),
      }
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Failed to confirm: ${text}`);
    }
  }

  async listThreads(): Promise<ThreadListResponse> {
    return api.get<ThreadListResponse>('/agent/threads');
  }

  async getThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
    return api.get<ThreadMessagesResponse>(
      `/agent/threads/${encodeURIComponent(threadId)}/messages`
    );
  }
}

export const agentChatService = new AgentChatService();
