import { getApiBase, getCliAuthHeaders } from './client';

export interface RemoteThreadSummary {
  id: string;
  title?: string | null;
  last_message_at?: string | null;
  updated_at?: string | null;
  source_project_id?: string | null;
}

export interface RemoteThreadMessage {
  role: string;
  content: string;
  tool_name: string | null;
  created_at: string;
}

export async function fetchThreads(): Promise<RemoteThreadSummary[]> {
  const res = await fetch(`${getApiBase()}/agent/threads`, {
    headers: getCliAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch threads: ${res.status}`);
  const data = (await res.json()) as { threads?: RemoteThreadSummary[] } | RemoteThreadSummary[];
  return Array.isArray(data) ? data : (data.threads ?? []);
}

export async function fetchThreadMessages(
  threadId: string
): Promise<RemoteThreadMessage[]> {
  const res = await fetch(`${getApiBase()}/agent/threads/${threadId}/messages`, {
    headers: getCliAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch messages: ${res.status}`);
  const data = (await res.json()) as { messages?: RemoteThreadMessage[] } | RemoteThreadMessage[];
  return Array.isArray(data) ? data : (data.messages ?? []);
}
