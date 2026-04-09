import { apiClient } from '@/services/apiClient';

function getStreamAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  try {
    const storageItem = localStorage.getItem('auth-storage');
    if (storageItem) {
      const parsed = JSON.parse(storageItem);
      const token = parsed?.state?.token;
      const orgId = parsed?.state?.organization?.id;
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (orgId) headers['X-Organization-ID'] = orgId;
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
    return apiClient.post<{ job_id: string }>('/agent/execute', request);
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
    return apiClient.get(`/agent/jobs/${encodeURIComponent(jobId)}`);
  }

  async confirmAction(
    jobId: string,
    confirmed: boolean
  ): Promise<{ status: string; job_id: string }> {
    return apiClient.post(`/agent/confirm/${encodeURIComponent(jobId)}`, {
      confirmed,
    });
  }

  async streamMessage(
    request: AgentExecuteRequest,
    callbacks: {
      onToken?: (content: string) => void;
      onToolStart?: (tool: string, args: Record<string, unknown>) => void;
      onToolEnd?: (tool: string, result: string) => void;
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
      onDone?: () => void;
      onError?: (error: string) => void;
    }
  ): Promise<void> {
    const headers = getStreamAuthHeaders();

    const response = await fetch('/api/v1/agent/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    });

    if (!response.ok || !response.body) {
      callbacks.onError?.(`Stream failed: ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
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
                  callbacks.onToolEnd?.(data.tool, data.result);
                  break;
                case 'rag_context':
                  callbacks.onRagContext?.(data.contexts);
                  break;
                case 'plan':
                  callbacks.onPlan?.(data.steps, data.reasoning);
                  break;
                case 'trace':
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
                  callbacks.onError?.(data.error);
                  break;
              }
            } catch {
              // Skip malformed JSON
            }
            eventType = '';
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async streamConfirm(
    request: { thread_id: string; confirmed: boolean },
    callbacks: {
      onToken?: (content: string) => void;
      onToolStart?: (tool: string, args: Record<string, unknown>) => void;
      onToolEnd?: (tool: string, result: string) => void;
      onConfirmation?: (
        threadId: string,
        confirmation: Record<string, unknown>
      ) => void;
      onDone?: () => void;
      onError?: (error: string) => void;
    }
  ): Promise<void> {
    const headers = getStreamAuthHeaders();

    const response = await fetch('/api/v1/agent/stream/confirm', {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    });

    if (!response.ok || !response.body) {
      callbacks.onError?.(`Stream confirm failed: ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
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
                  callbacks.onToolEnd?.(data.tool, data.result);
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
                  callbacks.onError?.(data.error);
                  break;
              }
            } catch {
              // Skip malformed JSON
            }
            eventType = '';
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async listThreads(): Promise<ThreadListResponse> {
    return apiClient.get<ThreadListResponse>('/agent/threads');
  }

  async getThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
    return apiClient.get<ThreadMessagesResponse>(
      `/agent/threads/${encodeURIComponent(threadId)}/messages`
    );
  }
}

export const agentChatService = new AgentChatService();
