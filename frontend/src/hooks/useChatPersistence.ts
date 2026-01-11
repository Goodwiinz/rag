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
    content?: string;  // Snippet content for preview
    source?: string;   // Document type/source
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
 * Extract title from snippet content (for legacy citations without document_title)
 * Handles various formats:
 * - "Title: Some Title Authors: ..." (arXiv structured format)
 * - "arXiv:2401.12345 - Paper Title" or "[2401.12345] Title"
 * - "DOI: 10.xxxx/xxxxx - Title"
 * - Plain text (first meaningful line)
 */
function extractTitleFromSnippet(snippet?: string): string | null {
  if (!snippet) return null;

  const trimmedSnippet = snippet.trim();

  // 1. Try to extract "Title: <title>" pattern (common in arXiv papers)
  const titleMatch = trimmedSnippet.match(/^Title:\s*(.+?)(?:\s*Authors:|$)/i);
  if (titleMatch && titleMatch[1]) {
    return titleMatch[1].trim();
  }

  // 2. Try arXiv ID formats: "arXiv:2401.12345 - Title" or "[2401.12345] Title"
  const arxivPatterns = [
    /arXiv:\d{4}\.\d{4,5}(?:v\d+)?\s*[-:]\s*(.+?)(?:\n|$)/i,
    /\[\d{4}\.\d{4,5}(?:v\d+)?\]\s*(.+?)(?:\n|$)/,
    /arXiv:\d{4}\.\d{4,5}(?:v\d+)?\s+(.+?)(?:\n|$)/i,
  ];
  for (const pattern of arxivPatterns) {
    const match = trimmedSnippet.match(pattern);
    if (match && match[1] && match[1].length > 5) {
      const extracted = match[1].trim();
      // Skip if it looks like an author list
      if (!extracted.match(/^[A-Z][a-z]+(?:\s+[A-Z]\.?\s*)+(?:,|and)/)) {
        return extracted.length > 150 ? extracted.slice(0, 147) + '...' : extracted;
      }
    }
  }

  // 3. Try DOI format: "DOI: 10.xxxx/xxxxx" followed by title
  const doiMatch = trimmedSnippet.match(/DOI:\s*10\.\S+\s*[-:]\s*(.+?)(?:\n|$)/i);
  if (doiMatch && doiMatch[1] && doiMatch[1].length > 5) {
    const extracted = doiMatch[1].trim();
    return extracted.length > 150 ? extracted.slice(0, 147) + '...' : extracted;
  }

  // 4. Try to skip metadata lines and find first content line
  const lines = trimmedSnippet.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  for (const line of lines) {
    // Skip lines that look like metadata
    if (line.match(/^(Authors?:|Date:|Published:|Source:|URL:|Abstract:)/i)) {
      continue;
    }
    // Skip lines that are just IDs or URLs
    if (line.match(/^(arXiv:|DOI:|https?:\/\/)/i)) {
      continue;
    }
    // Skip very short lines (likely not titles)
    if (line.length < 10) {
      continue;
    }
    // Use this line as title
    if (line.length <= 150) {
      return line;
    }
    return line.slice(0, 147) + '...';
  }

  // 5. Last resort: truncate snippet
  return trimmedSnippet.length > 80 ? trimmedSnippet.slice(0, 77) + '...' : trimmedSnippet;
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
    citations: dbMsg.citations?.map((c) => {
      // Build title with proper fallback chain:
      // 1. Explicit document_title from DB
      // 2. Extracted from snippet content
      // 3. External reference ID (e.g., arXiv ID like "2401.12345")
      // 4. Generic fallback
      const extractedTitle = extractTitleFromSnippet(c.snippet) || extractTitleFromSnippet(c.snippet_preview);
      const title = c.document_title
        ?? extractedTitle
        ?? (c.external_reference_id ? `Reference: ${c.external_reference_id}` : null)
        ?? 'Untitled Document';

      return {
        documentId: c.document_id || undefined,  // May be undefined for external refs
        externalReferenceId: c.external_reference_id || undefined,  // For arXiv IDs, etc.
        title,
        score: c.score || 0,
        content: c.snippet || c.snippet_preview,
        source: c.document_type,
      };
    }),
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

          // Select the first thread to load its messages (including citations)
          const threadsState = useChatStore.getState();
          const conversationThreads = threadsState.threads[conversationId] || [];
          if (conversationThreads.length > 0 && !threadsState.currentThreadId) {
            const firstThread = conversationThreads[0];
            console.log('[useChatPersistence] Selecting first thread:', firstThread.id);
            setCurrentThread(firstThread.id); // This triggers loadMessages
          }
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
  }, [isAuthenticated, token, initializeDefaultWorkspace, loadConversations, loadThreads, setCurrentConversation, setCurrentThread, createConversation]);

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
