import { getApiBase, getCliAuthHeaders } from './client';

export interface RemoteThreadSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_at: string | null;
  source_project_id: string | null;
  status: string;
  conversation_id: string;
}

export interface RemoteThreadMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
  tool_name: string | null;
  tool_call_id: string | null;
  citations: unknown[] | null;
  tool_executions: unknown[] | null;
}

export interface ThreadsClientOptions {
  fetchFn?: typeof fetch;
  signal?: AbortSignal;
}

export async function fetchThreads(
  options: ThreadsClientOptions = {}
): Promise<RemoteThreadSummary[]> {
  const { fetchFn = fetch, signal } = options;
  const res = await fetchFn(`${getApiBase()}/agent/threads`, {
    method: 'GET',
    headers: getCliAuthHeaders(),
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to list threads: ${res.status}`);
  }
  const body = (await res.json()) as { threads?: RemoteThreadSummary[] };
  return Array.isArray(body.threads) ? body.threads : [];
}

export async function fetchThreadMessages(
  threadId: string,
  options: ThreadsClientOptions = {}
): Promise<RemoteThreadMessage[]> {
  const { fetchFn = fetch, signal } = options;
  const res = await fetchFn(
    `${getApiBase()}/agent/threads/${encodeURIComponent(threadId)}/messages`,
    {
      method: 'GET',
      headers: getCliAuthHeaders(),
      signal,
    }
  );
  if (res.status === 404) {
    throw new Error('Thread not found');
  }
  if (!res.ok) {
    throw new Error(`Failed to load messages: ${res.status}`);
  }
  const body = (await res.json()) as { messages?: RemoteThreadMessage[] };
  return Array.isArray(body.messages) ? body.messages : [];
}
