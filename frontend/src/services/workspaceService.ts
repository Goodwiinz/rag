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
import { getPublicApiOrigin } from '@/utils/publicEndpoints';
import axios, { AxiosInstance } from 'axios';

const getAuthContext = async (): Promise<{
  token: string | null;
  organizationId: string | null;
}> => {
  if (typeof window === 'undefined') {
    return { token: null, organizationId: null };
  }

  try {
    const { createClient } = await import('@/lib/supabase/client');
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token ?? null;
    const organizationId =
      session?.user?.user_metadata?.organization_id ?? null;
    return { token, organizationId };
  } catch (e) {
    console.warn(
      '[WorkspaceService] Failed to get auth context from Supabase:',
      e
    );
    return { token: null, organizationId: null };
  }
};

const getDirectApiBaseUrl = (): string | null => {
  const configured = getPublicApiOrigin();
  return configured || null;
};

// Create a dedicated axios instance for v2 API
// Use empty baseURL to work with relative paths (goes through Next.js proxy)
// The API_PREFIX handles the /api/v2 path
const v2Client: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth interceptor for v2 client
v2Client.interceptors.request.use(async (config) => {
  // Only access Supabase on client-side
  if (typeof window === 'undefined') {
    return config;
  }

  try {
    const { token, organizationId } = await getAuthContext();

    console.debug(
      '[WorkspaceService] Token:',
      token ? `${token.substring(0, 20)}...` : 'none'
    );
    console.debug('[WorkspaceService] Org ID:', organizationId || 'none');

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (organizationId) {
      config.headers['X-Organization-ID'] = organizationId;
    }
  } catch (e) {
    console.warn('[WorkspaceService] Failed to get auth context:', e);
  }
  return config;
});

// Add response interceptor for better error handling
v2Client.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Fallback: if Next.js rewrite/proxy path fails at network layer, retry once
    // directly against NEXT_PUBLIC_API_URL.
    const isNetworkError =
      !error.response &&
      (error.code === 'ERR_NETWORK' ||
        /Network Error/i.test(error.message || ''));
    const originalConfig = error.config as
      | (typeof error.config & { _retryDirect?: boolean })
      | undefined;
    const directApiBaseUrl = getDirectApiBaseUrl();

    if (
      isNetworkError &&
      originalConfig &&
      !originalConfig._retryDirect &&
      directApiBaseUrl &&
      typeof originalConfig.url === 'string' &&
      originalConfig.url.startsWith('/api/v2/')
    ) {
      originalConfig._retryDirect = true;
      originalConfig.baseURL = directApiBaseUrl;
      console.warn(
        '[WorkspaceService] Proxy request failed, retrying direct API URL:',
        `${directApiBaseUrl}${originalConfig.url}`
      );
      return v2Client.request(originalConfig);
    }

    // Log detailed error info to help diagnose "Network Error" issues
    const errorInfo = {
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      method: error.config?.method,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      message: error.message,
      code: error.code,
      name: error.name,
    };

    // Filter out undefined values for cleaner logging
    const cleanedInfo = Object.fromEntries(
      Object.entries(errorInfo).filter(([_, v]) => v !== undefined)
    );

    // If no useful info, it's likely a network-level error
    if (Object.keys(cleanedInfo).length === 0) {
      console.error(
        '[WorkspaceService] Network error - backend may be unreachable:',
        error.toString?.() || error
      );
    } else {
      console.error('[WorkspaceService] Request failed:', cleanedInfo);
    }

    // If it's a 401, the user needs to re-authenticate (403 is forbidden, not unauthenticated)
    if (error.response?.status === 401) {
      console.warn('[WorkspaceService] Authentication error - logging out');
      // Dynamic import to avoid circular dependencies
      import('@/stores/authStore').then(({ useAuthStore }) => {
        useAuthStore.getState().signOut();
      });
    }

    return Promise.reject(error);
  }
);

const API_PREFIX = '/api/v2';

// ============================================================================
// Workspace Operations
// ============================================================================

export const workspaceService = {
  // Workspace CRUD
  async listWorkspaces(): Promise<Workspace[]> {
    const response = await v2Client.get<Workspace[]>(
      `${API_PREFIX}/workspaces`
    );
    return response.data;
  },

  async createWorkspace(data: WorkspaceCreate): Promise<Workspace> {
    const { organizationId } = await getAuthContext();
    const payload: WorkspaceCreate = {
      ...data,
      organization_id: data.organization_id || organizationId || undefined,
    };
    const response = await v2Client.post<Workspace>(
      `${API_PREFIX}/workspaces`,
      payload
    );
    return response.data;
  },

  async getWorkspace(workspaceId: string): Promise<WorkspaceDetail> {
    const response = await v2Client.get<WorkspaceDetail>(
      `${API_PREFIX}/workspaces/${workspaceId}`
    );
    return response.data;
  },

  async updateWorkspace(
    workspaceId: string,
    data: WorkspaceUpdate
  ): Promise<Workspace> {
    const response = await v2Client.patch<Workspace>(
      `${API_PREFIX}/workspaces/${workspaceId}`,
      data
    );
    return response.data;
  },

  async deleteWorkspace(workspaceId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/workspaces/${workspaceId}`);
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
    const response = await v2Client.get<ConversationListResponse>(url);
    return response.data;
  },

  async createConversation(data: ConversationCreate): Promise<Conversation> {
    // Use hierarchical path with workspace_id from request
    const response = await v2Client.post<Conversation>(
      `${API_PREFIX}/workspaces/${data.workspace_id}/conversations`,
      data
    );
    return response.data;
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    const response = await v2Client.get<Conversation>(
      `${API_PREFIX}/conversations/${conversationId}`
    );
    return response.data;
  },

  async updateConversation(
    conversationId: string,
    data: ConversationUpdate
  ): Promise<Conversation> {
    const response = await v2Client.patch<Conversation>(
      `${API_PREFIX}/conversations/${conversationId}`,
      data
    );
    return response.data;
  },

  async deleteConversation(conversationId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/conversations/${conversationId}`);
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
    const response = await v2Client.get<ThreadListResponse>(url);
    return response.data;
  },

  async createThread(data: ThreadCreate): Promise<Thread> {
    const response = await v2Client.post<Thread>(`${API_PREFIX}/threads`, data);
    return response.data;
  },

  async getThread(threadId: string): Promise<ThreadDetail> {
    const response = await v2Client.get<ThreadDetail>(
      `${API_PREFIX}/threads/${threadId}`
    );
    return response.data;
  },

  async updateThread(threadId: string, data: ThreadUpdate): Promise<Thread> {
    const response = await v2Client.patch<Thread>(
      `${API_PREFIX}/threads/${threadId}`,
      data
    );
    return response.data;
  },

  async deleteThread(threadId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/threads/${threadId}`);
  },

  async regenerateThreadSummary(threadId: string): Promise<Thread> {
    const response = await v2Client.post<Thread>(
      `${API_PREFIX}/threads/${threadId}/summarize`
    );
    return response.data;
  },

  // ============================================================================
  // Bulk Thread Operations
  // ============================================================================

  async bulkResolveThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    const response = await v2Client.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/resolve`,
      { thread_ids: threadIds }
    );
    return response.data;
  },

  async bulkArchiveThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    const response = await v2Client.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/archive`,
      { thread_ids: threadIds }
    );
    return response.data;
  },

  async bulkSummarizeThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    const response = await v2Client.post<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk/summarize`,
      { thread_ids: threadIds }
    );
    return response.data;
  },

  async bulkDeleteThreads(threadIds: string[]): Promise<BulkThreadResponse> {
    const response = await v2Client.delete<BulkThreadResponse>(
      `${API_PREFIX}/threads/bulk`,
      { data: { thread_ids: threadIds } }
    );
    return response.data;
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
    const response = await v2Client.get<ChatMessageListResponse>(url);
    return response.data;
  },

  async createMessage(data: ChatMessageCreate): Promise<ChatMessage> {
    const response = await v2Client.post<ChatMessage>(
      `${API_PREFIX}/messages`,
      data
    );
    return response.data;
  },

  async getMessage(messageId: string): Promise<ChatMessage> {
    const response = await v2Client.get<ChatMessage>(
      `${API_PREFIX}/messages/${messageId}`
    );
    return response.data;
  },

  async updateMessage(
    messageId: string,
    data: ChatMessageUpdate
  ): Promise<ChatMessage> {
    const response = await v2Client.patch<ChatMessage>(
      `${API_PREFIX}/messages/${messageId}`,
      data
    );
    return response.data;
  },

  async deleteMessage(messageId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/messages/${messageId}`);
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
    const response = await v2Client.get<CollectionListResponse>(url);
    return response.data;
  },

  async createCollection(data: CollectionCreate): Promise<Collection> {
    const response = await v2Client.post<Collection>(
      `${API_PREFIX}/collections`,
      data
    );
    return response.data;
  },

  async getCollection(collectionId: string): Promise<CollectionDetail> {
    const response = await v2Client.get<CollectionDetail>(
      `${API_PREFIX}/collections/${collectionId}`
    );
    return response.data;
  },

  async updateCollection(
    collectionId: string,
    data: CollectionUpdate
  ): Promise<Collection> {
    const response = await v2Client.patch<Collection>(
      `${API_PREFIX}/collections/${collectionId}`,
      data
    );
    return response.data;
  },

  async deleteCollection(collectionId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/collections/${collectionId}`);
  },

  async addDocumentsToCollection(
    collectionId: string,
    documentIds: string[]
  ): Promise<Collection> {
    const response = await v2Client.post<Collection>(
      `${API_PREFIX}/collections/${collectionId}/documents`,
      {
        document_ids: documentIds,
      }
    );
    return response.data;
  },

  async removeDocumentsFromCollection(
    collectionId: string,
    documentIds: string[]
  ): Promise<void> {
    await v2Client.delete(
      `${API_PREFIX}/collections/${collectionId}/documents`,
      {
        data: { document_ids: documentIds },
      }
    );
  },

  // ============================================================================
  // Chat Completion (AI-powered)
  // ============================================================================

  async sendChatCompletion(
    data: ChatCompletionRequest
  ): Promise<ChatCompletionResponse> {
    const response = await v2Client.post<ChatCompletionResponse>(
      `${API_PREFIX}/chat/completions`,
      data
    );
    return response.data;
  },

  // ============================================================================
  // Helper: Get or Create Default Workspace
  // ============================================================================

  async getOrCreateDefaultWorkspace(): Promise<Workspace> {
    // Check localStorage cache first to avoid unnecessary API calls
    if (typeof window !== 'undefined') {
      const cachedId = localStorage.getItem('default-workspace-id');
      const cachedAt = localStorage.getItem('default-workspace-cached-at');
      const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

      if (cachedId && cachedAt && Date.now() - Number(cachedAt) < TTL_MS) {
        try {
          const workspace = await this.getWorkspace(cachedId);
          return workspace;
        } catch (error: any) {
          // Any non-success from the cached-ID fetch (404 deleted, 403 no
          // access, 500 server confused) means the cache is no longer
          // trustworthy. Clear it and fall through to `listWorkspaces` —
          // otherwise the stale ID 500s on every page load.
          const status = error?.response?.status;
          if (status && status >= 400) {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-workspace-cached-at');
            if (status >= 500) {
              console.warn(
                '[WorkspaceService] Cached workspace fetch returned',
                status,
                '— clearing cache and re-listing workspaces'
              );
            }
          }
        }
      } else if (cachedId) {
        // TTL expired, clear stale cache
        localStorage.removeItem('default-workspace-id');
        localStorage.removeItem('default-workspace-cached-at');
      }
    }

    // Try to get existing workspaces with retry for transient errors
    let retries = 2;
    while (retries > 0) {
      try {
        const workspaces = await this.listWorkspaces();
        if (workspaces.length > 0) {
          // Return workspace with most content, or first available
          const bestWorkspace = workspaces.reduce((best, current) => {
            const bestScore =
              (best.collection_count ?? 0) + (best.conversation_count ?? 0);
            const currentScore =
              (current.collection_count ?? 0) +
              (current.conversation_count ?? 0);
            return currentScore > bestScore ? current : best;
          }, workspaces[0]);

          // Cache the ID
          if (typeof window !== 'undefined') {
            localStorage.setItem('default-workspace-id', bestWorkspace.id);
            localStorage.setItem(
              'default-workspace-cached-at',
              String(Date.now())
            );
          }
          return bestWorkspace;
        }
        // Only break if we successfully got an empty list (no workspaces exist)
        break;
      } catch (error: any) {
        retries--;
        if (retries > 0) {
          console.warn(
            '[WorkspaceService] Error listing workspaces, retrying...',
            error
          );
          await new Promise((resolve) => setTimeout(resolve, 500)); // Brief delay before retry
        } else {
          // Don't create workspace on error - rethrow to let caller handle
          console.error(
            '[WorkspaceService] Failed to list workspaces after retries:',
            error
          );
          throw error;
        }
      }
    }

    // Only create workspace if list was successfully empty
    console.log(
      '[WorkspaceService] No workspaces found, creating default workspace'
    );
    const newWorkspace = await this.createWorkspace({
      name: 'My Workspace',
      description: 'Default workspace for Terminal Observatory',
      is_public: false,
    });

    // Cache the new workspace ID
    if (typeof window !== 'undefined') {
      localStorage.setItem('default-workspace-id', newWorkspace.id);
      localStorage.setItem('default-workspace-cached-at', String(Date.now()));
    }

    return newWorkspace;
  },

  // ============================================================================
  // Helper: Get or Create Default Conversation
  // ============================================================================

  async getOrCreateDefaultConversation(
    workspaceId: string
  ): Promise<Conversation> {
    try {
      // Try to get existing conversations
      const response = await this.listConversations(workspaceId, { limit: 1 });
      if (response.conversations.length > 0) {
        return response.conversations[0];
      }
    } catch (error: any) {
      // Handle 404 - workspace not found or stale data
      if (error?.response?.status === 404) {
        console.warn(
          '[WorkspaceService] Workspace not found (404), clearing stale data'
        );
        if (typeof window !== 'undefined') {
          localStorage.removeItem('default-workspace-id');
          localStorage.removeItem('default-conversation-id');
        }
        // Let the caller handle retry with fresh workspace
        throw error;
      }
      console.warn('[WorkspaceService] Error listing conversations:', error);
    }

    // Create default conversation if none exists
    console.log('[WorkspaceService] Creating default conversation');
    return this.createConversation({
      workspace_id: workspaceId,
      title: 'New Chat',
      description: 'A new conversation',
    });
  },
};

export default workspaceService;
