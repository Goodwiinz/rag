import { api } from '@/services/api-client';
import { createClient } from '@/lib/supabase/client';

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

export interface AgentExecuteRequest {
  messages: Array<{ role: string; content: string }>;
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

class AgentChatService {
  async startJob(request: AgentExecuteRequest): Promise<{ job_id: string }> {
    return api.post<{ job_id: string }>('/agent/execute', request);
  }

  async pollJob(jobId: string): Promise<{
    status: 'running' | 'completed' | 'failed' | 'awaiting_confirmation';
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
    callbacks: {
      onToken?: (content: string) => void;
      onToolStart?: (tool: string, args: Record<string, unknown>) => void;
      onToolEnd?: (tool: string, result: string, isError: boolean) => void;
      onRagContext?: (contexts: Array<Record<string, unknown>>) => void;
      onPlan?: (
        steps: Array<Record<string, unknown>>,
        reasoning: string
      ) => void;
      onReflection?: (passed: boolean, issues: string[], round: number) => void;
      onConfirmation?: (
        threadId: string,
        confirmation: Record<string, unknown>
      ) => void;
      onTrace?: (threadId: string) => void;
      onDone?: () => void;
      onError?: (error: string) => void;
    },
    signal?: AbortSignal
  ): Promise<void> {
    const headers = await getStreamAuthHeaders();

    let response: Response;
    try {
      response = await fetch('/api/v1/agent/stream', {
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
      // Read the backend's error body so the user sees the real cause,
      // not just an HTTP number. FastAPI usually returns `{detail: "..."}`.
      let backendMessage = '';
      try {
        const text = await response.text();
        if (text) {
          try {
            const parsed = JSON.parse(text);
            const raw = parsed?.detail || parsed?.error || parsed?.message || text;
            backendMessage = typeof raw === 'string' ? raw : (raw?.message || JSON.stringify(raw));
          } catch {
            backendMessage = text.slice(0, 500);
          }
        }
      } catch {
        // Ignore — fall back to status code only.
      }
      callbacks.onError?.(
        backendMessage
          ? `Stream failed (${response.status}): ${backendMessage}`
          : `Stream failed: ${response.status}`
      );
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let eventType = '';

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
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              switch (eventType) {
                case 'token':
                  callbacks.onToken?.(data.content);
                  break;
                case 'tool_start':
                  callbacks.onToolStart?.(data.tool, data.args);
                  break;
                case 'tool_end':
                  callbacks.onToolEnd?.(
                    data.tool,
                    data.result,
                    Boolean(data.is_error)
                  );
                  break;
                case 'rag_context':
                  callbacks.onRagContext?.(data.contexts);
                  break;
                case 'plan':
                  callbacks.onPlan?.(data.steps, data.reasoning);
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
                    data.round
                  );
                  break;
                case 'confirmation':
                  callbacks.onConfirmation?.(data.thread_id, data.confirmation);
                  break;
                case 'done':
                  callbacks.onDone?.();
                  break;
                case 'error':
                  callbacks.onError?.(typeof data.error === 'string' ? data.error : String(data.error?.message || JSON.stringify(data.error)));
                  break;
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      throw err;
    } finally {
      reader.releaseLock();
    }
  }

  async streamConfirm(
    request: { thread_id: string; confirmed: boolean },
    callbacks: {
      onToken?: (content: string) => void;
      onToolStart?: (tool: string, args: Record<string, unknown>) => void;
      onToolEnd?: (tool: string, result: string, isError: boolean) => void;
      onConfirmation?: (
        threadId: string,
        confirmation: Record<string, unknown>
      ) => void;
      onDone?: () => void;
      onError?: (error: string) => void;
    },
    signal?: AbortSignal
  ): Promise<void> {
    const headers = await getStreamAuthHeaders();

    let response: Response;
    try {
      response = await fetch('/api/v1/agent/stream/confirm', {
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
      let backendMessage = '';
      try {
        const text = await response.text();
        if (text) {
          try {
            const parsed = JSON.parse(text);
            const raw = parsed?.detail || parsed?.error || parsed?.message || text;
            backendMessage = typeof raw === 'string' ? raw : (raw?.message || JSON.stringify(raw));
          } catch {
            backendMessage = text.slice(0, 500);
          }
        }
      } catch {
        // Ignore — fall back to status code only.
      }
      callbacks.onError?.(
        backendMessage
          ? `Stream confirm failed (${response.status}): ${backendMessage}`
          : `Stream confirm failed: ${response.status}`
      );
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let eventType = '';

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
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              switch (eventType) {
                case 'token':
                  callbacks.onToken?.(data.content);
                  break;
                case 'tool_start':
                  callbacks.onToolStart?.(data.tool, data.args);
                  break;
                case 'tool_end':
                  callbacks.onToolEnd?.(
                    data.tool,
                    data.result,
                    Boolean(data.is_error)
                  );
                  break;
                case 'trace':
                  break;
                case 'confirmation':
                  callbacks.onConfirmation?.(data.thread_id, data.confirmation);
                  break;
                case 'done':
                  callbacks.onDone?.();
                  break;
                case 'error':
                  callbacks.onError?.(typeof data.error === 'string' ? data.error : String(data.error?.message || JSON.stringify(data.error)));
                  break;
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      throw err;
    } finally {
      reader.releaseLock();
    }
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
