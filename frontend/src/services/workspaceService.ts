/**
 * Workspace Service for Terminal Observatory thread-centric chat system
 * Communicates with backend /api/v2/workspaces/* endpoints
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import {
  Workspace,
  WorkspaceCreate,
  WorkspaceUpdate,
  WorkspaceDetail,
  Conversation,
  ConversationCreate,
  ConversationUpdate,
  ConversationListResponse,
  Thread,
  ThreadCreate,
  ThreadUpdate,
  ThreadDetail,
  ThreadListResponse,
  ChatMessage,
  ChatMessageCreate,
  ChatMessageUpdate,
  ChatMessageListResponse,
  Collection,
  CollectionCreate,
  CollectionUpdate,
  CollectionDetail,
  CollectionListResponse,
  ChatCompletionRequest,
  ChatCompletionResponse,
} from '@/types/workspace';

// Create a dedicated axios instance for v2 API (not using apiClient which has /api/v1 base)
const API_V2_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';

const v2Client: AxiosInstance = axios.create({
  baseURL: API_V2_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth interceptor for v2 client
v2Client.interceptors.request.use((config) => {
  // Only access localStorage on client-side
  if (typeof window === 'undefined') {
    return config;
  }

  let token: string | null = null;
  let organizationId: string | null = null;

  try {
    // Try Zustand persist storage first (auth-storage)
    const authStorage = localStorage.getItem('auth-storage');
    if (authStorage) {
      const auth = JSON.parse(authStorage);
      token = auth.state?.token;
      organizationId = auth.state?.organization?.id || auth.state?.user?.organization_id;
    }

    // Fallback to legacy localStorage keys
    if (!token) {
      token = localStorage.getItem('access_token');
      const userData = localStorage.getItem('user_data');
      if (userData) {
        const user = JSON.parse(userData);
        organizationId = organizationId || user.organization_id;
      }
    }

    console.debug('[WorkspaceService] Token:', token ? `${token.substring(0, 20)}...` : 'none');
    console.debug('[WorkspaceService] Org ID:', organizationId || 'none');

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (organizationId) {
      config.headers['X-Organization-ID'] = organizationId;
    }
  } catch (e) {
    console.warn('[WorkspaceService] Failed to parse auth storage:', e);
  }
  return config;
});

const API_PREFIX = '/api/v2';

// ============================================================================
// Workspace Operations
// ============================================================================

export const workspaceService = {
  // Workspace CRUD
  async listWorkspaces(): Promise<Workspace[]> {
    const response = await v2Client.get<Workspace[]>(`${API_PREFIX}/workspaces`);
    return response.data;
  },

  async createWorkspace(data: WorkspaceCreate): Promise<Workspace> {
    const response = await v2Client.post<Workspace>(`${API_PREFIX}/workspaces`, data);
    return response.data;
  },

  async getWorkspace(workspaceId: string): Promise<WorkspaceDetail> {
    const response = await v2Client.get<WorkspaceDetail>(`${API_PREFIX}/workspaces/${workspaceId}`);
    return response.data;
  },

  async updateWorkspace(workspaceId: string, data: WorkspaceUpdate): Promise<Workspace> {
    const response = await v2Client.patch<Workspace>(`${API_PREFIX}/workspaces/${workspaceId}`, data);
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
    const response = await v2Client.get<Conversation>(`${API_PREFIX}/conversations/${conversationId}`);
    return response.data;
  },

  async updateConversation(conversationId: string, data: ConversationUpdate): Promise<Conversation> {
    const response = await v2Client.patch<Conversation>(`${API_PREFIX}/conversations/${conversationId}`, data);
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
    const response = await v2Client.get<ThreadDetail>(`${API_PREFIX}/threads/${threadId}`);
    return response.data;
  },

  async updateThread(threadId: string, data: ThreadUpdate): Promise<Thread> {
    const response = await v2Client.patch<Thread>(`${API_PREFIX}/threads/${threadId}`, data);
    return response.data;
  },

  async deleteThread(threadId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/threads/${threadId}`);
  },

  // ============================================================================
  // Message Operations
  // ============================================================================

  async listMessages(
    threadId: string,
    options: { page?: number; limit?: number } = {}
  ): Promise<ChatMessageListResponse> {
    const params = new URLSearchParams();
    if (options.page) params.append('page', options.page.toString());
    if (options.limit) params.append('limit', options.limit.toString());

    const queryString = params.toString();
    const url = `${API_PREFIX}/threads/${threadId}/messages${queryString ? `?${queryString}` : ''}`;
    const response = await v2Client.get<ChatMessageListResponse>(url);
    return response.data;
  },

  async createMessage(data: ChatMessageCreate): Promise<ChatMessage> {
    const response = await v2Client.post<ChatMessage>(`${API_PREFIX}/messages`, data);
    return response.data;
  },

  async getMessage(messageId: string): Promise<ChatMessage> {
    const response = await v2Client.get<ChatMessage>(`${API_PREFIX}/messages/${messageId}`);
    return response.data;
  },

  async updateMessage(messageId: string, data: ChatMessageUpdate): Promise<ChatMessage> {
    const response = await v2Client.patch<ChatMessage>(`${API_PREFIX}/messages/${messageId}`, data);
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
    const response = await v2Client.post<Collection>(`${API_PREFIX}/collections`, data);
    return response.data;
  },

  async getCollection(collectionId: string): Promise<CollectionDetail> {
    const response = await v2Client.get<CollectionDetail>(`${API_PREFIX}/collections/${collectionId}`);
    return response.data;
  },

  async updateCollection(collectionId: string, data: CollectionUpdate): Promise<Collection> {
    const response = await v2Client.patch<Collection>(`${API_PREFIX}/collections/${collectionId}`, data);
    return response.data;
  },

  async deleteCollection(collectionId: string): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/collections/${collectionId}`);
  },

  async addDocumentsToCollection(collectionId: string, documentIds: string[]): Promise<Collection> {
    const response = await v2Client.post<Collection>(`${API_PREFIX}/collections/${collectionId}/documents`, {
      document_ids: documentIds,
    });
    return response.data;
  },

  async removeDocumentsFromCollection(collectionId: string, documentIds: string[]): Promise<void> {
    await v2Client.delete(`${API_PREFIX}/collections/${collectionId}/documents`, {
      data: { document_ids: documentIds },
    });
  },

  // ============================================================================
  // Chat Completion (AI-powered)
  // ============================================================================

  async sendChatCompletion(data: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    const response = await v2Client.post<ChatCompletionResponse>(`${API_PREFIX}/chat/completions`, data);
    return response.data;
  },

  // ============================================================================
  // Helper: Get or Create Default Workspace
  // ============================================================================

  async getOrCreateDefaultWorkspace(): Promise<Workspace> {
    try {
      // Try to get existing workspaces
      const workspaces = await this.listWorkspaces();
      if (workspaces.length > 0) {
        // Return the first (most recent) workspace
        return workspaces[0];
      }
    } catch (error) {
      console.warn('[WorkspaceService] Error listing workspaces:', error);
    }

    // Create default workspace if none exists
    console.log('[WorkspaceService] Creating default workspace');
    return this.createWorkspace({
      name: 'My Workspace',
      description: 'Default workspace for Terminal Observatory',
      is_public: false,
    });
  },

  // ============================================================================
  // Helper: Get or Create Default Conversation
  // ============================================================================

  async getOrCreateDefaultConversation(workspaceId: string): Promise<Conversation> {
    try {
      // Try to get existing conversations
      const response = await this.listConversations(workspaceId, { limit: 1 });
      if (response.conversations.length > 0) {
        return response.conversations[0];
      }
    } catch (error) {
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
