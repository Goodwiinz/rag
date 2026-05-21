/**
 * Workspace Service for Terminal Observatory thread-centric chat system
 * Communicates with backend /api/v2/workspaces/* endpoints
 */

import {
  BulkThreadResponse,
  ChatCompletionRequest,
  ChatCompletionResponse,
  ChatMessage,
  ChatMessageCreate,
  ChatMessageListResponse,
  ChatMessageUpdate,
  Collection,
  CollectionCreate,
  CollectionDetail,
  CollectionListResponse,
  CollectionUpdate,
  Conversation,
  ConversationCreate,
  ConversationListResponse,
  ConversationUpdate,
  Thread,
  ThreadCreate,
  ThreadDetail,
  ThreadListResponse,
  ThreadUpdate,
  Workspace,
  WorkspaceCreate,
  WorkspaceDetail,
  WorkspaceUpdate,
} from '@/types/workspace';
import { api } from '@/services/api-client';

const API_PREFIX = '/api/v2';

const WS_CACHE_KEY = 'default-workspace-object';
const WS_CACHE_AT_KEY = 'default-workspace-cached-at';
const WS_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

/** Clear all workspace service caches (localStorage). Called on auth errors. */
export function clearWorkspaceServiceCache(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(WS_CACHE_KEY);
    localStorage.removeItem(WS_CACHE_AT_KEY);
    localStorage.removeItem('default-workspace-id');
    localStorage.removeItem('default-conversation-id');
    localStorage.removeItem('chat-storage');
  }
}

// ============================================================================
// Workspace Operations
// ============================================================================

export const workspaceService = {
  // Workspace CRUD
  async listWorkspaces(): Promise<Workspace[]> {
    return api.get<Workspace[]>(`${API_PREFIX}/workspaces`);
  },

  async createWorkspace(data: WorkspaceCreate): Promise<Workspace> {
    return api.post<Workspace>(`${API_PREFIX}/workspaces`, data);
  },

  async getWorkspace(workspaceId: string): Promise<WorkspaceDetail> {
    return api.get<WorkspaceDetail>(
      `${API_PREFIX}/workspaces/${workspaceId}`
    );
  },

  async updateWorkspace(
    workspaceId: string,
    data: WorkspaceUpdate
  ): Promise<Workspace> {
    return api.patch<Workspace>(
      `${API_PREFIX}/workspaces/${workspaceId}`,
      data
    );
  },

  async deleteWorkspace(workspaceId: string): Promise<void> {
    await api.delete(`${API_PREFIX}/workspaces/${workspaceId}`);
  },

  // ============================================================================
  // Conversation Operations
  // ============================================================================

  async listConversations(
    workspaceId: string,
    options: { page?: number; limit?: number; search?: string } = {}
  ): Promise<ConversationListResponse> {
    const params = new URLSearchParams();
    if (options.page) params.append('page', options.page.toString());
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.search) params.append('search', options.search);

    const queryString = params.toString();
    const url = `${API_PREFIX}/workspaces/${workspaceId}/conversations${queryString ? `?${queryString}` : ''}`;
    return api.get<ConversationListResponse>(url);
  },

  async createConversation(data: ConversationCreate): Promise<Conversation> {
    return api.post<Conversation>(
      `${API_PREFIX}/workspaces/${data.workspace_id}/conversations`,
      data
    );
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    return api.get<Conversation>(
      `${API_PREFIX}/conversations/${conversationId}`
    );
  },

  async updateConversation(
    conversationId: string,
    data: ConversationUpdate
  ): Promise<Conversation> {
    return api.patch<Conversation>(
      `${API_PREFIX}/conversations/${conversationId}`,
      data
    );
  },

  async deleteConversation(conversationId: string): Promise<void> {
    await api.delete(`${API_PREFIX}/conversations/${conversationId}`);
  },

  // ============================================================================
  // Thread Operations
  // ============================================================================

  async listThreads(
    conversationId: string,
    options: { page?: number; limit?: number } = {}
  ): Promise<ThreadListResponse> {
    const params = new URLSearchParams();
    if (options.page) params.append('page', options.page.toString());
    if (options.limit) params.append('limit', options.limit.toString());

    const queryString = params.toString();
    const url = `${API_PREFIX}/conversations/${conversationId}/threads${queryString ? `?${queryString}` : ''}`;
    return api.get<ThreadListResponse>(url);
  },

  async createThread(data: ThreadCreate): Promise<Thread> {
    return api.post<Thread>(`${API_PREFIX}/threads`, data);
  },

  async getThread(threadId: string): Promise<ThreadDetail> {
    return api.get<ThreadDetail>(`${API_PREFIX}/threads/${threadId}`);
  },

  async updateThread(threadId: string, data: ThreadUpdate): Promise<Thread> {
    return api.patch<Thread>(`${API_PREFIX}/threads/${threadId}`, data);
  },

  async deleteThread(threadId: string): Promise<void> {
    await api.delete(`${API_PREFIX}/threads/${threadId}`);
  },

  async regenerateThreadSummary(threadId: string): Promise<Thread> {
    return api.post<Thread>(`${API_PREFIX}/threads/${threadId}/summarize`);
  },

  // ============================================================================
  // Bulk Thread Operations
  // ============================================================================

  async bulkResolveThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    return api.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/resolve`,
      { thread_ids: threadIds }
    );
  },

  async bulkArchiveThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    return api.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/archive`,
      { thread_ids: threadIds }
    );
  },

  async bulkSummarizeThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    return api.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/summarize`,
      { thread_ids: threadIds }
    );
  },

  async bulkDeleteThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    return api.request<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_ids: threadIds }),
      }
    );
  },

  // ============================================================================
  // Message Operations
  // ============================================================================

  async listMessages(
    threadId: string,
    options: { page?: number; limit?: number; offset?: number } = {}
  ): Promise<ChatMessageListResponse> {
    const params = new URLSearchParams();
    if (options.page) params.append('page', options.page.toString());
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset !== undefined) {
      params.append('offset', options.offset.toString());
    }

    const queryString = params.toString();
    const url = `${API_PREFIX}/threads/${threadId}/messages${queryString ? `?${queryString}` : ''}`;
    return api.get<ChatMessageListResponse>(url);
  },

  async createMessage(data: ChatMessageCreate): Promise<ChatMessage> {
    return api.post<ChatMessage>(`${API_PREFIX}/messages`, data);
  },

  async getMessage(messageId: string): Promise<ChatMessage> {
    return api.get<ChatMessage>(`${API_PREFIX}/messages/${messageId}`);
  },

  async updateMessage(
    messageId: string,
    data: ChatMessageUpdate
  ): Promise<ChatMessage> {
    return api.patch<ChatMessage>(
      `${API_PREFIX}/messages/${messageId}`,
      data
    );
  },

  async deleteMessage(messageId: string): Promise<void> {
    await api.delete(`${API_PREFIX}/messages/${messageId}`);
  },

  // ============================================================================
  // Collection Operations
  // ============================================================================

  async listCollections(
    workspaceId: string,
    options: { page?: number; limit?: number } = {}
  ): Promise<CollectionListResponse> {
    const params = new URLSearchParams();
    if (options.page) params.append('page', options.page.toString());
    if (options.limit) params.append('limit', options.limit.toString());

    const queryString = params.toString();
    const url = `${API_PREFIX}/workspaces/${workspaceId}/collections${queryString ? `?${queryString}` : ''}`;
    return api.get<CollectionListResponse>(url);
  },

  async createCollection(data: CollectionCreate): Promise<Collection> {
    return api.post<Collection>(`${API_PREFIX}/collections`, data);
  },

  async getCollection(collectionId: string): Promise<CollectionDetail> {
    return api.get<CollectionDetail>(
      `${API_PREFIX}/collections/${collectionId}`
    );
  },

  async updateCollection(
    collectionId: string,
    data: CollectionUpdate
  ): Promise<Collection> {
    return api.patch<Collection>(
      `${API_PREFIX}/collections/${collectionId}`,
      data
    );
  },

  async deleteCollection(collectionId: string): Promise<void> {
    await api.delete(`${API_PREFIX}/collections/${collectionId}`);
  },

  async addDocumentsToCollection(
    collectionId: string,
    documentIds: string[]
  ): Promise<Collection> {
    return api.post<Collection>(
      `${API_PREFIX}/collections/${collectionId}/documents`,
      { document_ids: documentIds }
    );
  },

  async removeDocumentsFromCollection(
    collectionId: string,
    documentIds: string[]
  ): Promise<void> {
    await api.request(
      `${API_PREFIX}/collections/${collectionId}/documents`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: documentIds }),
      }
    );
  },

  // ============================================================================
  // Chat Completion (AI-powered)
  // ============================================================================

  async sendChatCompletion(
    data: ChatCompletionRequest
  ): Promise<ChatCompletionResponse> {
    return api.post<ChatCompletionResponse>(
      `${API_PREFIX}/chat/completions`,
      data
    );
  },

  // ============================================================================
  // Helper: Get or Create Default Workspace
  // ============================================================================

  async getOrCreateDefaultWorkspace(): Promise<Workspace> {
    const cacheWorkspace = (ws: Workspace) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem(WS_CACHE_KEY, JSON.stringify(ws));
        localStorage.setItem(WS_CACHE_AT_KEY, String(Date.now()));
        localStorage.setItem('default-workspace-id', ws.id);
      }
    };

    const clearCachedWorkspace = () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem(WS_CACHE_KEY);
        localStorage.removeItem(WS_CACHE_AT_KEY);
        localStorage.removeItem('default-workspace-id');
      }
    };

    // Check localStorage for a cached full workspace object — avoids any API call on warm hits.
    if (typeof window !== 'undefined') {
      const cachedJson = localStorage.getItem(WS_CACHE_KEY);
      const cachedAt = localStorage.getItem(WS_CACHE_AT_KEY);

      if (
        cachedJson &&
        cachedAt &&
        Date.now() - Number(cachedAt) < WS_CACHE_TTL_MS
      ) {
        try {
          const cachedWorkspace = JSON.parse(cachedJson) as Partial<Workspace>;

          if (cachedWorkspace.id) {
            try {
              const workspace = await this.getWorkspace(cachedWorkspace.id);
              cacheWorkspace(workspace);
              return workspace;
            } catch (error: unknown) {
              const apiError = error as { error?: { status_code?: number } };
              const status = apiError?.error?.status_code;
              if (status === 403 || status === 404) {
                clearCachedWorkspace();
              }
            }
          } else {
            clearCachedWorkspace();
          }
        } catch {
          // Corrupted JSON — fall through to API
          clearCachedWorkspace();
        }
      } else if (cachedJson) {
        // TTL expired — clear stale entry
        clearCachedWorkspace();
      }
    }

    // Try to get existing workspaces with retry for transient errors
    let retries = 2;
    while (retries > 0) {
      try {
        const workspaces = await this.listWorkspaces();
        if (workspaces.length > 0) {
          const bestWorkspace = workspaces.reduce((best, current) => {
            const bestScore =
              (best.collection_count ?? 0) + (best.conversation_count ?? 0);
            const currentScore =
              (current.collection_count ?? 0) +
              (current.conversation_count ?? 0);
            return currentScore > bestScore ? current : best;
          }, workspaces[0]);

          cacheWorkspace(bestWorkspace);
          return bestWorkspace;
        }
        // Successfully got an empty list — no workspaces exist yet
        break;
      } catch (error: unknown) {
        retries--;
        if (retries > 0) {
          console.warn(
            '[WorkspaceService] Error listing workspaces, retrying...',
            error
          );
          await new Promise((resolve) => setTimeout(resolve, 500));
        } else {
          console.error(
            '[WorkspaceService] Failed to list workspaces after retries:',
            error
          );
          throw error;
        }
      }
    }

    console.log(
      '[WorkspaceService] No workspaces found, creating default workspace'
    );
    const newWorkspace = await this.createWorkspace({
      name: 'My Workspace',
      description: 'Default workspace for Terminal Observatory',
      is_public: false,
    });

    cacheWorkspace(newWorkspace);
    return newWorkspace;
  },

  // ============================================================================
  // Helper: Get or Create Default Conversation
  // ============================================================================

  async getOrCreateDefaultConversation(
    workspaceId: string
  ): Promise<Conversation> {
    const cacheConversationId = (id: string) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('default-conversation-id', id);
      }
    };

    try {
      const response = await this.listConversations(workspaceId, { limit: 1 });
      if (response.conversations.length > 0) {
        const conv = response.conversations[0];
        cacheConversationId(conv.id);
        return conv;
      }
    } catch (error: unknown) {
      const apiError = error as { error?: { status_code?: number } };
      const status = apiError?.error?.status_code;
      if (status === 404) {
        console.warn(
          '[WorkspaceService] Workspace not found (404), clearing stale data'
        );
        if (typeof window !== 'undefined') {
          localStorage.removeItem(WS_CACHE_KEY);
          localStorage.removeItem(WS_CACHE_AT_KEY);
          localStorage.removeItem('default-workspace-id');
          localStorage.removeItem('default-conversation-id');
        }
        throw error;
      }
      console.warn('[WorkspaceService] Error listing conversations:', error);
    }

    console.log('[WorkspaceService] Creating default conversation');
    const conv = await this.createConversation({
      workspace_id: workspaceId,
      title: 'New Chat',
      description: 'A new conversation',
    });
    cacheConversationId(conv.id);
    return conv;
  },
};

export default workspaceService;
