/**
 * useChatPersistence Hook
 *
 * A React hook that bridges the chat store with existing UI components.
 * Provides a simplified interface for chat persistence operations.
 */

import { useEffect, useCallback, useMemo, useRef } from 'react';
import { useChatStore, selectCurrentMessages, selectCurrentThread } from '@/store/chat-store';
import { workspaceService } from '@/services/workspaceService';
import { useAuthStore } from '@/stores/authStore';
import {
  Thread,
  ChatMessage,
  MessageRole,
  ThreadStatus,
} from '@/types/workspace';

// UI Message type for compatibility with existing components
export interface UIMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Array<{
    documentId?: string;  // Optional: may be undefined for external references
    externalReferenceId?: string;  // For non-database references (e.g., arXiv IDs)
    title: string;
    score: number;
  }>;
}

// UI Conversation type for compatibility with existing components
export interface UIConversation {
  id: string;
  title: string;
  messages: UIMessage[];
  modelId?: string;
  createdAt: number;
  updatedAt: number;
  threadId: string;
  conversationId: string;
  tags?: string[];
  isBookmarked?: boolean;
  isArchived?: boolean;
}

interface UseChatPersistenceReturn {
  // State
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;

  // Current selections
  currentWorkspaceId: string | null;
  currentConversationId: string | null;
  currentThreadId: string | null;

  // Data (UI-formatted)
  conversations: UIConversation[];
  messages: UIMessage[];

  // Actions
  initialize: () => Promise<void>;
  createNewChat: () => Promise<string | null>;
  selectConversation: (id: string) => void;
  sendMessage: (content: string) => Promise<UIMessage | null>;
  deleteConversation: (id: string) => Promise<boolean>;
  renameConversation: (id: string, title: string) => Promise<boolean>;
  archiveConversation: (id: string) => Promise<boolean>;
}

/**
 * Map database message to UI message format
 */
function mapDbMessageToUI(dbMsg: ChatMessage): UIMessage {
  return {
    id: dbMsg.id,
    role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
    content: dbMsg.content,
    timestamp: new Date(dbMsg.created_at).getTime(),
    citations: dbMsg.citations?.map((c) => ({
      documentId: c.document_id || undefined,  // May be undefined for external refs
      externalReferenceId: c.external_reference_id || undefined,  // For arXiv IDs, etc.
      title: c.document_title || 'Unknown Document',
      score: c.score || 0,
    })),
  };
}

/**
 * Map thread to UI conversation format
 */
function mapThreadToUIConversation(
  thread: Thread,
  messages: ChatMessage[],
  conversationId: string
): UIConversation {
  return {
    id: thread.id,
    title: thread.title || 'New Chat',
    messages: messages.map(mapDbMessageToUI),
    createdAt: new Date(thread.created_at).getTime(),
    updatedAt: new Date(thread.updated_at).getTime(),
    threadId: thread.id,
    conversationId: conversationId,
    isArchived: thread.status === ThreadStatus.ARCHIVED,
  };
}

export function useChatPersistence(): UseChatPersistenceReturn {
  const { isAuthenticated, token } = useAuthStore();

  // Prevent multiple initialization attempts
  const initializationRef = useRef<{ started: boolean; completed: boolean }>({
    started: false,
    completed: false,
  });

  // Store state
  const {
    currentWorkspaceId,
    currentConversationId,
    currentThreadId,
    workspaces,
    conversations: storeConversations,
    threads,
    messages: storeMessages,
    isLoadingWorkspaces,
    isLoadingConversations,
    isLoadingThreads,
    isLoadingMessages,
    isSendingMessage,
    error,
    // Actions
    initializeDefaultWorkspace,
    loadConversations,
    loadThreads,
    loadMessages,
    createThread,
    createConversation,
    sendMessage: storeSendMessage,
    setCurrentWorkspace,
    setCurrentConversation,
    setCurrentThread,
    updateThread,
    deleteThread,
    clearError,
  } = useChatStore();

  // Derived loading state
  const isLoading = isLoadingWorkspaces || isLoadingConversations || isLoadingThreads || isLoadingMessages || isSendingMessage;

  // Check if initialized
  const isInitialized = !!currentWorkspaceId && workspaces.length > 0;

  // Map threads to UI conversations
  const uiConversations = useMemo((): UIConversation[] => {
    if (!currentConversationId) {
      console.log('[useChatPersistence] No currentConversationId, returning empty');
      return [];
    }

    const conversationThreads = threads[currentConversationId] || [];
    console.log('[useChatPersistence] Mapping threads for conversation:', currentConversationId, 'threads:', conversationThreads.length);

    return conversationThreads.map((thread) => {
      const threadMessages = storeMessages[thread.id] || [];
      return mapThreadToUIConversation(thread, threadMessages, currentConversationId);
    });
  }, [currentConversationId, threads, storeMessages]);

  // Get current messages
  const currentMessages = useMemo((): UIMessage[] => {
    if (!currentThreadId) return [];
    const threadMessages = storeMessages[currentThreadId] || [];
    return threadMessages.map(mapDbMessageToUI);
  }, [currentThreadId, storeMessages]);

  // Initialize workspace and conversation
  const initialize = useCallback(async () => {
    // Guard against multiple initializations
    if (initializationRef.current.started) {
      console.log('[useChatPersistence] Initialization already started, skipping');
      return;
    }

    if (!isAuthenticated || !token) {
      console.log('[useChatPersistence] Not authenticated, skipping initialization');
      return;
    }

    initializationRef.current.started = true;

    try {
      console.log('[useChatPersistence] Starting initialization...');
      await initializeDefaultWorkspace();

      const state = useChatStore.getState();
      console.log('[useChatPersistence] After initializeDefaultWorkspace, workspaceId:', state.currentWorkspaceId);

      // Load conversations for the current workspace
      if (state.currentWorkspaceId) {
        await loadConversations(state.currentWorkspaceId);

        const updatedState = useChatStore.getState();
        const workspaceConversations = updatedState.conversations[state.currentWorkspaceId] || [];
        console.log('[useChatPersistence] Loaded conversations:', workspaceConversations.length);

        // Select first conversation if available
        let conversationId = updatedState.currentConversationId;
        console.log('[useChatPersistence] Current conversationId:', conversationId);

        if (workspaceConversations.length > 0 && !conversationId) {
          conversationId = workspaceConversations[0].id;
          console.log('[useChatPersistence] Setting first conversation:', conversationId);
          setCurrentConversation(conversationId);
        } else if (workspaceConversations.length === 0) {
          // Create default conversation
          console.log('[useChatPersistence] No conversations, creating new one...');
          const newConv = await createConversation({
            workspace_id: state.currentWorkspaceId,
            title: 'New Chat',
          });
          if (newConv) {
            conversationId = newConv.id;
            setCurrentConversation(newConv.id);
          }
        }

        // Load threads for the selected conversation
        if (conversationId) {
          console.log('[useChatPersistence] Loading threads for conversation:', conversationId);
          await loadThreads(conversationId);
        } else {
          console.log('[useChatPersistence] No conversationId to load threads for');
        }
      } else {
        console.log('[useChatPersistence] No workspaceId after initialization');
      }

      initializationRef.current.completed = true;
      console.log('[useChatPersistence] Initialization complete');
    } catch (error) {
      console.error('[useChatPersistence] Initialization failed:', error);
      initializationRef.current.started = false; // Allow retry on error
    }
  }, [isAuthenticated, token, initializeDefaultWorkspace, loadConversations, loadThreads, setCurrentConversation, createConversation]);

  // Create new chat (thread)
  const createNewChat = useCallback(async (): Promise<string | null> => {
    let conversationId = currentConversationId;

    // If no conversation exists, create one first
    if (!conversationId) {
      console.log('[useChatPersistence] No conversation, creating one first...');

      if (!currentWorkspaceId) {
        console.error('[useChatPersistence] No workspace available');
        return null;
      }

      const newConv = await createConversation({
        workspace_id: currentWorkspaceId,
        title: 'New Chat',
      });

      if (newConv) {
        conversationId = newConv.id;
        setCurrentConversation(newConv.id);
      } else {
        console.error('[useChatPersistence] Failed to create conversation');
        return null;
      }
    }

    try {
      const thread = await createThread({
        conversation_id: conversationId,
        title: 'New Chat',
      });

      if (thread) {
        setCurrentThread(thread.id);
        return thread.id;
      }
      return null;
    } catch (error) {
      console.error('[useChatPersistence] Failed to create new chat:', error);
      return null;
    }
  }, [currentConversationId, currentWorkspaceId, createConversation, createThread, setCurrentConversation, setCurrentThread]);

  // Select conversation (thread in our UI mapping)
  const selectConversation = useCallback((id: string) => {
    setCurrentThread(id);
  }, [setCurrentThread]);

  // Send message
  const sendMessage = useCallback(async (content: string): Promise<UIMessage | null> => {
    if (!currentThreadId && !currentConversationId) {
      console.error('[useChatPersistence] No thread or conversation selected');
      return null;
    }

    // If no thread exists, create one first
    let threadId = currentThreadId;
    if (!threadId && currentConversationId) {
      const newThread = await createThread({
        conversation_id: currentConversationId,
        title: content.substring(0, 50),
      });
      if (newThread) {
        threadId = newThread.id;
        setCurrentThread(newThread.id);
      }
    }

    if (!threadId) {
      console.error('[useChatPersistence] Failed to get or create thread');
      return null;
    }

    const message = await storeSendMessage(content, threadId);

    if (message) {
      return mapDbMessageToUI(message);
    }
    return null;
  }, [currentThreadId, currentConversationId, createThread, setCurrentThread, storeSendMessage]);

  // Delete conversation (thread)
  const deleteConversation = useCallback(async (id: string): Promise<boolean> => {
    return await deleteThread(id);
  }, [deleteThread]);

  // Rename conversation (thread)
  const renameConversation = useCallback(async (id: string, title: string): Promise<boolean> => {
    const result = await updateThread(id, { title });
    return !!result;
  }, [updateThread]);

  // Archive conversation (thread)
  const archiveConversation = useCallback(async (id: string): Promise<boolean> => {
    const result = await updateThread(id, { status: ThreadStatus.ARCHIVED });
    return !!result;
  }, [updateThread]);

  // Reset initialization ref when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      initializationRef.current = { started: false, completed: false };
    }
  }, [isAuthenticated]);

  // Auto-initialize on mount - use ref guard instead of initialize in deps to prevent loops
  useEffect(() => {
    if (isAuthenticated && !initializationRef.current.started && !initializationRef.current.completed) {
      initialize();
    }
  }, [isAuthenticated, initialize]);

  return {
    isInitialized,
    isLoading,
    error,
    currentWorkspaceId,
    currentConversationId,
    currentThreadId,
    conversations: uiConversations,
    messages: currentMessages,
    initialize,
    createNewChat,
    selectConversation,
    sendMessage,
    deleteConversation,
    renameConversation,
    archiveConversation,
  };
}

export default useChatPersistence;
