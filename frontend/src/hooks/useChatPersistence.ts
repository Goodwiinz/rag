/**
 * useChatPersistence Hook
 *
 * A React hook that bridges the chat store with existing UI components.
 * Provides a simplified interface for chat persistence operations.
 */

import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import {
  ChatMessage,
  MessageRole,
  Thread,
  ThreadStatus,
} from '@/types/workspace';
import { useCallback, useEffect, useMemo, useRef } from 'react';

const debugLog =
  process.env.NODE_ENV === 'development'
    ? (...args: unknown[]) => console.log(...args)
    : () => {};

// UI Message type for compatibility with existing components
export interface UIMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Array<{
    documentId?: string; // Optional: may be undefined for external references
    externalReferenceId?: string; // For non-database references (e.g., arXiv IDs)
    title: string;
    score: number;
    content?: string; // Snippet content for preview
    source?: string; // Document type/source
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

// Pattern configuration for title extraction
const TITLE_PATTERNS: Array<{
  pattern: RegExp;
  group: number;
  minLength?: number;
  skipAuthorCheck?: boolean;
}> = [
  // "Title: <title>" pattern (common in arXiv papers)
  {
    pattern: /^Title:\s*(.+?)(?:\s*Authors:|$)/i,
    group: 1,
    skipAuthorCheck: true,
  },
  // arXiv ID formats: "arXiv:2401.12345 - Title"
  {
    pattern: /arXiv:\d{4}\.\d{4,5}(?:v\d+)?\s*[-:]\s*(.+?)(?:\n|$)/i,
    group: 1,
    minLength: 5,
  },
  // arXiv bracket format: "[2401.12345] Title"
  {
    pattern: /\[\d{4}\.\d{4,5}(?:v\d+)?\]\s*(.+?)(?:\n|$)/,
    group: 1,
    minLength: 5,
  },
  // arXiv with space: "arXiv:2401.12345 Title"
  {
    pattern: /arXiv:\d{4}\.\d{4,5}(?:v\d+)?\s+(.+?)(?:\n|$)/i,
    group: 1,
    minLength: 5,
  },
  // DOI format: "DOI: 10.xxxx/xxxxx - Title"
  { pattern: /DOI:\s*10\.\S+\s*[-:]\s*(.+?)(?:\n|$)/i, group: 1, minLength: 5 },
];

// Metadata patterns to skip when looking for title lines
const METADATA_SKIP_PATTERNS = [
  /^(Authors?:|Date:|Published:|Source:|URL:|Abstract:)/i,
  /^(arXiv:|DOI:|https?:\/\/)/i,
];

/**
 * Truncate text to max length with ellipsis
 */
function truncateTitle(text: string, maxLength: number = 150): string {
  return text.length > maxLength ? text.slice(0, maxLength - 3) + '...' : text;
}

/**
 * Check if text looks like an author list
 */
function looksLikeAuthorList(text: string): boolean {
  return /^[A-Z][a-z]+(?:\s+[A-Z]\.?\s*)+(?:,|and)/.test(text);
}

function extractTitleFromSnippet(snippet?: string): string | null {
  if (!snippet) return null;

  const trimmedSnippet = snippet.trim();
  if (!trimmedSnippet) return null;

  // Try configured patterns
  for (const {
    pattern,
    group,
    minLength = 0,
    skipAuthorCheck = false,
  } of TITLE_PATTERNS) {
    const match = trimmedSnippet.match(pattern);
    if (match?.[group] && match[group].length > minLength) {
      const extracted = match[group].trim();
      // Skip if it looks like an author list (unless configured to skip this check)
      if (!skipAuthorCheck && looksLikeAuthorList(extracted)) {
        continue;
      }
      return truncateTitle(extracted);
    }
  }

  // Fallback: Try to skip metadata lines and find first content line
  const lines = trimmedSnippet
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  for (const line of lines) {
    // Skip lines matching metadata patterns
    if (METADATA_SKIP_PATTERNS.some((p) => p.test(line))) {
      continue;
    }
    // Skip very short lines (likely not titles)
    if (line.length < 10) {
      continue;
    }
    return truncateTitle(line);
  }

  // Last resort: truncate snippet
  return truncateTitle(trimmedSnippet, 80);
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
      const extractedTitle =
        extractTitleFromSnippet(c.snippet) ||
        extractTitleFromSnippet(c.snippet_preview);
      const title =
        c.document_title ??
        extractedTitle ??
        (c.external_reference_id
          ? `Reference: ${c.external_reference_id}`
          : null) ??
        'Untitled Document';

      return {
        documentId: c.document_id || undefined, // May be undefined for external refs
        externalReferenceId: c.external_reference_id || undefined, // For arXiv IDs, etc.
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
  const isLoading =
    isLoadingWorkspaces ||
    isLoadingConversations ||
    isLoadingThreads ||
    isLoadingMessages ||
    isSendingMessage;

  // Check if initialized
  const isInitialized = !!currentWorkspaceId && workspaces.length > 0;

  // Map threads to UI conversations
  const uiConversations = useMemo((): UIConversation[] => {
    if (!currentConversationId) {
      debugLog(
        '[useChatPersistence] No currentConversationId, returning empty'
      );
      return [];
    }

    const conversationThreads = threads[currentConversationId] || [];
    debugLog(
      '[useChatPersistence] Mapping threads for conversation:',
      currentConversationId,
      'threads:',
      conversationThreads.length
    );

    return conversationThreads.map((thread) => {
      const threadMessages = storeMessages[thread.id] || [];
      return mapThreadToUIConversation(
        thread,
        threadMessages,
        currentConversationId
      );
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
      debugLog('[useChatPersistence] Initialization already started, skipping');
      return;
    }

    if (!isAuthenticated || !token) {
      debugLog(
        '[useChatPersistence] Not authenticated, skipping initialization'
      );
      return;
    }

    initializationRef.current.started = true;

    try {
      debugLog('[useChatPersistence] Starting initialization...');
      await initializeDefaultWorkspace();

      const state = useChatStore.getState();
      debugLog(
        '[useChatPersistence] After initializeDefaultWorkspace, workspaceId:',
        state.currentWorkspaceId
      );

      // Load conversations for the current workspace
      if (state.currentWorkspaceId) {
        await loadConversations(state.currentWorkspaceId);

        const updatedState = useChatStore.getState();
        const workspaceConversations =
          updatedState.conversations[state.currentWorkspaceId] || [];
        debugLog(
          '[useChatPersistence] Loaded conversations:',
          workspaceConversations.length
        );

        // Select first conversation if available
        let conversationId = updatedState.currentConversationId;
        debugLog(
          '[useChatPersistence] Current conversationId:',
          conversationId
        );

        if (workspaceConversations.length > 0 && !conversationId) {
          conversationId = workspaceConversations[0].id;
          debugLog(
            '[useChatPersistence] Setting first conversation:',
            conversationId
          );
          setCurrentConversation(conversationId);
        } else if (workspaceConversations.length === 0) {
          // Create default conversation
          debugLog(
            '[useChatPersistence] No conversations, creating new one...'
          );
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
          debugLog(
            '[useChatPersistence] Loading threads for conversation:',
            conversationId
          );
          await loadThreads(conversationId);

          // Select the first thread to load its messages (including citations)
          const threadsState = useChatStore.getState();
          const conversationThreads =
            threadsState.threads[conversationId] || [];
          if (conversationThreads.length > 0 && !threadsState.currentThreadId) {
            const firstThread = conversationThreads[0];
            debugLog(
              '[useChatPersistence] Selecting first thread:',
              firstThread.id
            );
            setCurrentThread(firstThread.id); // This triggers loadMessages
          }
        } else {
          debugLog(
            '[useChatPersistence] No conversationId to load threads for'
          );
        }
      } else {
        debugLog('[useChatPersistence] No workspaceId after initialization');
      }

      initializationRef.current.completed = true;
      debugLog('[useChatPersistence] Initialization complete');
    } catch (error) {
      console.error('[useChatPersistence] Initialization failed:', error);
      initializationRef.current.started = false; // Allow retry on error
    }
  }, [
    isAuthenticated,
    token,
    initializeDefaultWorkspace,
    loadConversations,
    loadThreads,
    setCurrentConversation,
    setCurrentThread,
    createConversation,
  ]);

  // Create new chat (thread)
  const createNewChat = useCallback(async (): Promise<string | null> => {
    debugLog('[useChatPersistence] createNewChat called', {
      currentConversationId,
      currentWorkspaceId,
      isInitialized: !!currentWorkspaceId,
    });

    let conversationId = currentConversationId;

    // If no conversation exists, create one first
    if (!conversationId) {
      debugLog('[useChatPersistence] No conversation, creating one first...');

      if (!currentWorkspaceId) {
        console.error(
          '[useChatPersistence] No workspace available - make sure to call initialize() first'
        );
        return null;
      }

      const newConv = await createConversation({
        workspace_id: currentWorkspaceId,
        title: 'New Chat',
      });

      if (newConv) {
        conversationId = newConv.id;
        setCurrentConversation(newConv.id);
        debugLog('[useChatPersistence] Created conversation:', newConv.id);
      } else {
        console.error(
          '[useChatPersistence] Failed to create conversation - API may have returned null'
        );
        return null;
      }
    }

    try {
      debugLog(
        '[useChatPersistence] Creating thread for conversation:',
        conversationId
      );
      const thread = await createThread({
        conversation_id: conversationId,
        title: 'New Chat',
      });

      if (thread) {
        debugLog(
          '[useChatPersistence] Thread created successfully:',
          thread.id
        );
        setCurrentThread(thread.id);
        return thread.id;
      }
      console.error(
        '[useChatPersistence] createThread returned null/undefined - check network tab for API errors'
      );
      return null;
    } catch (error) {
      console.error('[useChatPersistence] Failed to create new chat:', error);
      return null;
    }
  }, [
    currentConversationId,
    currentWorkspaceId,
    createConversation,
    createThread,
    setCurrentConversation,
    setCurrentThread,
  ]);

  // Select conversation (thread in our UI mapping)
  const selectConversation = useCallback(
    (id: string) => {
      setCurrentThread(id);
    },
    [setCurrentThread]
  );

  // Send message
  const sendMessage = useCallback(
    async (content: string): Promise<UIMessage | null> => {
      if (!currentThreadId && !currentConversationId) {
        console.error(
          '[useChatPersistence] No thread or conversation selected'
        );
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
    },
    [
      currentThreadId,
      currentConversationId,
      createThread,
      setCurrentThread,
      storeSendMessage,
    ]
  );

  // Delete conversation (thread)
  const deleteConversation = useCallback(
    async (id: string): Promise<boolean> => {
      return await deleteThread(id);
    },
    [deleteThread]
  );

  // Rename conversation (thread)
  const renameConversation = useCallback(
    async (id: string, title: string): Promise<boolean> => {
      const result = await updateThread(id, { title });
      return !!result;
    },
    [updateThread]
  );

  // Archive conversation (thread)
  const archiveConversation = useCallback(
    async (id: string): Promise<boolean> => {
      const result = await updateThread(id, { status: ThreadStatus.ARCHIVED });
      return !!result;
    },
    [updateThread]
  );

  // Reset initialization ref when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      initializationRef.current = { started: false, completed: false };
    }
  }, [isAuthenticated]);

  // Auto-initialize on mount - use ref guard instead of initialize in deps to prevent loops
  useEffect(() => {
    if (
      isAuthenticated &&
      !initializationRef.current.started &&
      !initializationRef.current.completed
    ) {
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
