import { loadConfig, saveConfig } from './auth/store';
import { getApiBase, getCliAuthHeaders } from './services/client';

export type StreamEvent =
  | { type: 'token'; content: string }
  | { type: 'tool_start'; tool: string }
  | { type: 'tool_end'; tool: string; isError: boolean }
  | { type: 'confirmation'; threadId: string; details: Record<string, unknown> }
  | { type: 'plan'; steps: string[]; reasoning: string }
  | { type: 'reflection'; passed: boolean; issues: string[]; round: number }
  | { type: 'rag_context'; contexts: Array<Record<string, unknown>> }
  | { type: 'done' }
  | { type: 'error'; message: string };

export interface StreamOptions {
  fetchFn?: typeof fetch;
  signal?: AbortSignal;
}

function persistThreadId(threadId: string): void {
  const cfg = loadConfig();
  if (cfg && cfg.thread_id !== threadId) {
    saveConfig({ ...cfg, thread_id: threadId });
  }
}

async function* _parseSseBody(
  body: ReadableStream<Uint8Array>,
  onTrace?: (threadId: string) => void
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let eventType = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          const raw = line.slice(5).trim();
          try {
            const data = JSON.parse(raw);
            if (eventType === 'token' && data.content) {
              yield { type: 'token', content: data.content };
            } else if (eventType === 'tool_start') {
              yield { type: 'tool_start', tool: data.tool };
            } else if (eventType === 'tool_end') {
              yield {
                type: 'tool_end',
                tool: data.tool,
                isError: data.is_error ?? false,
              };
            } else if (eventType === 'confirmation') {
              yield {
                type: 'confirmation',
                threadId: data.thread_id,
                details: data.confirmation ?? {},
              };
            } else if (eventType === 'plan') {
              yield {
                type: 'plan',
                steps: Array.isArray(data.steps) ? data.steps : [],
                reasoning: typeof data.reasoning === 'string' ? data.reasoning : '',
              };
            } else if (eventType === 'reflection') {
              yield {
                type: 'reflection',
                passed: data.passed ?? true,
                issues: Array.isArray(data.issues) ? data.issues : [],
                round: typeof data.round === 'number' ? data.round : 0,
              };
            } else if (eventType === 'rag_context') {
              yield {
                type: 'rag_context',
                contexts: Array.isArray(data.contexts) ? data.contexts : [],
              };
            } else if (eventType === 'trace' && data.thread_id) {
              onTrace?.(data.thread_id);
            } else if (eventType === 'done') {
              yield { type: 'done' };
              return;
            } else if (eventType === 'error') {
              yield { type: 'error', message: data.error ?? 'Unknown error' };
              return;
            }
          } catch {
            /* skip malformed SSE data */
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function* streamAgent(
  message: string,
  pageContext: Record<string, unknown> = {},
  options: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
  const config = loadConfig();
  if (!config) throw new Error('Not logged in');

  const { fetchFn = fetch, signal } = options;
  const headers = getCliAuthHeaders();

  const res = await fetchFn(`${getApiBase()}/agent/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      messages: [{ role: 'user', content: message }],
      page_context: pageContext,
      thread_id: config.thread_id ?? undefined,
    }),
    signal,
  });

  if (!res.ok || !res.body) {
    yield { type: 'error', message: `Stream failed: ${res.status}` };
    return;
  }

  yield* _parseSseBody(res.body, persistThreadId);
}

export async function* streamConfirm(
  threadId: string,
  confirmed: boolean,
  options: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
  const config = loadConfig();
  if (!config) throw new Error('Not logged in');

  const { fetchFn = fetch, signal } = options;
  const headers = getCliAuthHeaders();

  const res = await fetchFn(`${getApiBase()}/agent/stream/confirm`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ thread_id: threadId, confirmed }),
    signal,
  });

  if (!res.ok || !res.body) {
    yield { type: 'error', message: `Confirm failed: ${res.status}` };
    return;
  }

  yield* _parseSseBody(res.body, persistThreadId);
}
