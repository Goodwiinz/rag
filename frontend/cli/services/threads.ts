import { getApiBase, getCliAuthHeaders } from './client';
import { appendFileSync, existsSync, mkdirSync } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { loadMessages, type CachedMessage } from './messageStore';

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

export interface ThreadMessagesView {
  source: 'cache' | 'cache+server' | 'server';
  messages: Array<CachedMessage | RemoteThreadMessage>;
}

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), '.nous');
}

function threadJsonlPath(id: string): string {
  return path.join(configDir(), 'threads', `${id}.jsonl`);
}

function appendRemoteToCache(
  threadId: string,
  remote: RemoteThreadMessage[]
): void {
  const conversation = remote.filter(
    (m) => m.role.toLowerCase() === 'user' || m.role.toLowerCase() === 'assistant'
  );
  if (conversation.length === 0) return;
  const file = threadJsonlPath(threadId);
  const dir = path.dirname(file);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const lines = conversation.map((m) => {
    const cached: CachedMessage = {
      role: m.role.toLowerCase() === 'user' ? 'user' : 'assistant',
      content: m.content,
      ended_at: m.created_at,
    };
    return JSON.stringify(cached);
  });
  appendFileSync(file, lines.join('\n') + '\n', 'utf-8');
}

/**
 * Load thread messages, preferring the local JSONL cache and reconciling with
 * the server when the registry's `last_message_at` mismatches the cache.
 *
 * TODO(Task 9): once the backend exposes `GET /threads/:id/messages?since=...`,
 * pass `since=<latest local ended_at>` to fetch a delta instead of the full
 * conversation, and append the delta into the local cache.
 */
export async function loadThreadMessagesWithCache(
  threadId: string,
  serverLastMessageAt: string | null,
  options: ThreadsClientOptions = {}
): Promise<ThreadMessagesView> {
  const local = loadMessages(threadId);
  const latestLocal = local.length > 0 ? local[local.length - 1].ended_at : null;

  // Cache hit: local has data and matches server's high-water mark.
  if (
    local.length > 0 &&
    latestLocal &&
    serverLastMessageAt &&
    latestLocal === serverLastMessageAt
  ) {
    return { source: 'cache', messages: local };
  }

  // Cache miss / stale: fetch from server. ?since= delta is Task 9's territory;
  // for now we fetch the full conversation and reconcile.
  const remote = await fetchThreadMessages(threadId, options);

  // If we had local data, only append truly-newer remote turns to the cache.
  if (local.length > 0 && latestLocal) {
    const newer = remote.filter((m) => m.created_at > latestLocal);
    if (newer.length > 0) appendRemoteToCache(threadId, newer);
    return { source: 'cache+server', messages: [...local, ...newer] };
  }

  // No local cache yet — seed it with whatever the server has and return that.
  appendRemoteToCache(threadId, remote);
  return { source: 'server', messages: remote };
}
