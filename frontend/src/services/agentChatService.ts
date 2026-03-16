import { apiClient } from '@/services/apiClient';

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
  }>;
  total: number;
}

class AgentChatService {
  async execute(request: AgentExecuteRequest): Promise<AgentExecuteResponse> {
    return apiClient.post<AgentExecuteResponse>(
      '/api/v1/agent/execute',
      request
    );
  }

  async listThreads(): Promise<ThreadListResponse> {
    return apiClient.get<ThreadListResponse>('/api/v1/agent/threads');
  }

  async getThreadMessages(threadId: string): Promise<ThreadMessagesResponse> {
    return apiClient.get<ThreadMessagesResponse>(
      `/api/v1/agent/threads/${threadId}/messages`
    );
  }
}

export const agentChatService = new AgentChatService();
