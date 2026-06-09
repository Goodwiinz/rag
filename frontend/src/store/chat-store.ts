/**
 * Chat Store - Zustand store for NOUS thread-centric chat system
 * Manages workspace, conversation, thread, and message state with persistence
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { enableMapSet } from 'immer';

// Enable Immer's MapSet plugin for Set/Map support in state
enableMapSet();
import {
  BulkThreadResponse,
  Workspace,
  WorkspaceCreate,
  WorkspaceUpdate,
  Conversation,
  ConversationCreate,
  ConversationUpdate,
  Thread,
  ThreadCreate,
  ThreadUpdate,
  ChatMessage,
  ChatMessageUpdate,
  ThreadStatus,
} from '@/types/workspace';
import { workspaceService } from '@/services/workspaceService';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generic helper to remove an item from a record of arrays by ID.
 * Used for deleting conversations, threads, and messages from their respective records.
 *
 * PERFORMANCE (GOO-86): Now uses O(1) lookup via reverse index instead of O(n*m) iteration.
 * Falls back to O(n*m) iteration if reverse index not provided (backward compatibility).
 *
 * @param record - The record containing arrays (e.g., conversations keyed by workspaceId)
 * @param itemId - The ID of the item to remove
 * @param reverseIndex - Optional reverse index mapping itemId to parentKey for O(1) lookup
 * @returns true if item was found and removed, false otherwise
 */
function removeItemFromRecord<T extends { id: string }>(
  record: Record<string, T[]>,
  itemId: string,
  reverseIndex?: Record<string, string>
): boolean {
  // O(1) path: use reverse index if available
  if (reverseIndex) {
    const parentKey = reverseIndex[itemId];
    if (parentKey && record[parentKey]) {
      const index = record[parentKey].findIndex((item) => item.id === itemId);
      if (index !== -1) {
        record[parentKey].splice(index, 1);
        delete reverseIndex[itemId];
        return true;
      }
    }
    return false;
  }

  // O(n*m) fallback: iterate all keys (legacy behavior)
  for (const key of Object.keys(record)) {
    const index = record[key]?.findIndex((item) => item.id === itemId);
    if (index !== undefined && index !== -1) {
      record[key].splice(index, 1);
      return true;
    }
  }
  return false;
}

/**
 * O(1) helper to update an item in a nested record structure using a reverse index.
 * Used by bulk update operations (resolve, archive) for performance (GOO-86).
 *
 * @param record - The record containing arrays (e.g., threads keyed by conversationId)
 * @param itemId - The ID of the item to update
 * @param newItem - The updated item to replace the existing one
 * @param reverseIndex - Optional reverse index mapping itemId to parentKey for O(1) lookup
 * @returns true if item was found and updated, false otherwise
 */
function updateItemInRecord<T extends { id: string }>(
  record: Record<string, T[]>,
  itemId: string,
  newItem: T,
  reverseIndex?: Record<string, string>
): boolean {
  // O(1) path: use reverse index if available
  if (reverseIndex) {
    const parentKey = reverseIndex[itemId];
    if (parentKey && record[parentKey]) {
      const index = record[parentKey].findIndex((item) => item.id === itemId);
      if (index !== -1) {
        record[parentKey][index] = newItem;
        return true;
      }
    }
    return false;
  }

  // O(n*m) fallback: iterate all keys (legacy behavior)
  for (const key of Object.keys(record)) {
    const index = record[key]?.findIndex((item) => item.id === itemId);
    if (index !== undefined && index !== -1) {
      record[key][index] = newItem;
      return true;
    }
  }
  return false;
}

// ============================================================================
// State Types
// ============================================================================

interface ChatState {
  // Current selections
  currentWorkspaceId: string | null;
  currentConversationId: string | null;
  currentThreadId: string | null;

  // Data
  workspaces: Workspace[];
  conversations: Record<string, Conversation[]>; // keyed by workspace_id
  threads: Record<string, Thread[]>; // keyed by conversation_id
  messages: Record<string, ChatMessage[]>; // keyed by thread_id

  // Reverse indexes for O(1) parent lookup (GOO-86 performance fix)
  conversationToWorkspace: Record<string, string>; // conversation_id -> workspace_id
  threadToConversation: Record<string, string>; // thread_id -> conversation_id
  messageToThread: Record<string, string>; // message_id -> thread_id

  // Loading states
  isLoadingWorkspaces: boolean;
  isLoadingConversations: boolean;
  isLoadingThreads: boolean;
  isLoadingMessages: boolean;
  isSendingMessage: boolean;

  // Reinitialization guard for 404 recovery
  isReinitializing: boolean;
  reinitRetryCount: number;

  // Error states
  error: string | null;

  // UI states
  shortcutsDialogOpen: boolean;
  copiedMessageId: string | null;
  sidebarCollapsed: boolean;
  selectedModel: string;

  // Bulk selection state
  selectedThreadIds: Set<string>;
  isSelectMode: boolean;

  // Streaming state
  isStreaming: boolean;
  streamingContent: string;
  streamingMessageId: string | null;
  streamingCitations: Array<Record<string, unknown>>;
  streamingDiagnosticsTraceId: string | null;
  // True only while RAG retrieval is in flight (set at stream start, cleared on
  // the first token or rag_context event). Drives the composer's
  // "reading sources…" status phase.
  isRetrievingRag: boolean;
}

interface ChatActions {
  // Selection actions
  setCurrentWorkspace: (workspaceId: string | null) => void;
  setCurrentConversation: (conversationId: string | null) => void;
  setCurrentThread: (threadId: string | null) => void;
  setThreadProjectBinding: (threadId: string, projectId: string | null) => void;
  getThreadById: (threadId: string | null) => Thread | undefined;

  // Workspace actions
  loadWorkspaces: () => Promise<void>;
  createWorkspace: (data: WorkspaceCreate) => Promise<Workspace | null>;
  updateWorkspace: (
    id: string,
    data: WorkspaceUpdate
  ) => Promise<Workspace | null>;
  deleteWorkspace: (id: string) => Promise<boolean>;

  // Conversation actions
  loadConversations: (workspaceId: string) => Promise<void>;
  createConversation: (
    data: ConversationCreate
  ) => Promise<Conversation | null>;
  updateConversation: (
    id: string,
    data: ConversationUpdate
  ) => Promise<Conversation | null>;
  deleteConversation: (id: string) => Promise<boolean>;

  // Thread actions
  loadThreads: (conversationId: string) => Promise<void>;
  createThread: (data: ThreadCreate) => Promise<Thread | null>;
  updateThread: (id: string, data: ThreadUpdate) => Promise<Thread | null>;
  deleteThread: (id: string) => Promise<boolean>;
  resolveThread: (id: string) => Promise<Thread | null>;
  reopenThread: (id: string) => Promise<Thread | null>;

  // Bulk thread actions
  toggleSelectMode: () => void;
  toggleThreadSelection: (threadId: string) => void;
  selectAllThreads: (threadIds?: string[]) => void;
  clearSelection: () => void;
  bulkResolveThreads: () => Promise<BulkThreadResponse | null>;
  bulkArchiveThreads: () => Promise<BulkThreadResponse | null>;
  bulkSummarizeThreads: () => Promise<BulkThreadResponse | null>;
  bulkDeleteThreads: () => Promise<BulkThreadResponse | null>;

  // Message actions
  loadMessages: (threadId: string) => Promise<void>;
  sendMessage: (
    content: string,
    threadId?: string
  ) => Promise<ChatMessage | null>;
  addMessageToStore: (threadId: string, message: ChatMessage) => void;
  updateMessageFeedback: (
    id: string,
    data: ChatMessageUpdate
  ) => Promise<ChatMessage | null>;
  deleteMessage: (id: string) => Promise<boolean>;
  clearThread: (threadId: string) => void;

  // UI actions
  setShortcutsDialogOpen: (open: boolean) => void;
  setSelectedModel: (model: string) => void;
  setCopiedMessageId: (id: string | null) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Streaming actions
  streamMessage: (
    content: string,
    threadId?: string,
    useRag?: boolean
  ) => Promise<void>;
  stopStreaming: () => void;

  // Utility actions
  clearError: () => void;
  reset: () => void;
  initializeDefaultWorkspace: () => Promise<void>;
}

type ChatStore = ChatState & ChatActions;

// ============================================================================
// Initial State
// ============================================================================

// Maximum retry attempts for reinitialization to prevent infinite loops
const MAX_REINIT_RETRIES = 3;

// Maximum number of thread message caches to retain in memory.
// When exceeded, the oldest threads (by key insertion order) are evicted.
const MAX_CACHED_THREADS = 50;

// Helper type for the recovery handler
type RecoveryResult =
  | { shouldProceed: false }
  | { shouldProceed: true; triggerReinit: () => void };

/**
 * Helper to handle stale data recovery (404 errors) atomically.
 * Performs guard check and state update in a single set() call to prevent race conditions.
 *
 * @param get - Zustand get function
 * @param set - Zustand set function (immer-wrapped)
 * @param context - Context string for logging
 * @param options - Additional options for state clearing
 * @returns RecoveryResult with shouldProceed and optional reinit trigger
 */
function handleStaleDataRecovery(
  get: () => ChatState & ChatActions,
  set: (fn: (state: ChatState) => void) => void,
  context: string,
  options: {
    clearWorkspaces?: boolean;
    loadingKey?:
      | 'isLoadingConversations'
      | 'isLoadingThreads'
      | 'isLoadingMessages';
  } = {}
): RecoveryResult {
  const { clearWorkspaces = true, loadingKey } = options;

  let shouldReinit = false;
  let maxRetriesReached = false;

  // Perform guard check AND state update atomically in a single set() call
  set((state) => {
    // Guard against concurrent/repeated reinitialization and infinite loops
    if (
      state.isReinitializing ||
      state.reinitRetryCount >= MAX_REINIT_RETRIES
    ) {
      console.warn(
        `[ChatStore] Skipping reinitialization for ${context} (already in progress or max retries reached)`
      );
      maxRetriesReached = state.reinitRetryCount >= MAX_REINIT_RETRIES;
      if (loadingKey) {
        state[loadingKey] = false;
      }
      if (maxRetriesReached) {
        state.error = 'Failed to initialize workspace after multiple attempts';
      }
      return;
    }

    // Clear stale data and set reinitialization flag atomically
    shouldReinit = true;
    state.currentWorkspaceId = null;
    state.currentConversationId = null;
    state.currentThreadId = null;
    if (clearWorkspaces) {
      state.workspaces = [];
    }
    if (loadingKey) {
      state[loadingKey] = false;
    }
    state.isReinitializing = true;
    state.reinitRetryCount += 1;
    state.error = null;
  });

  if (!shouldReinit) {
    return { shouldProceed: false };
  }

  // Return a trigger function that the caller can use to start reinitialization
  return {
    shouldProceed: true,
    triggerReinit: () => {
      // Use Promise-based approach instead of fire-and-forget setTimeout
      (async () => {
        try {
          await get().initializeDefaultWorkspace();
        } catch (err) {
          console.error(
            `[ChatStore] Reinitialization failed for ${context}:`,
            err
          );
        } finally {
          set((state) => {
            state.isReinitializing = false;
          });
        }
      })();
    },
  };
}

const initialState: ChatState = {
  currentWorkspaceId: null,
  currentConversationId: null,
  currentThreadId: null,
  workspaces: [],
  conversations: {},
  threads: {},
  messages: {},
  // Reverse indexes for O(1) lookup
  conversationToWorkspace: {},
  threadToConversation: {},
  messageToThread: {},
  isLoadingWorkspaces: false,
  isLoadingConversations: false,
  isLoadingThreads: false,
  isLoadingMessages: false,
  isSendingMessage: false,
  isReinitializing: false,
  reinitRetryCount: 0,
  error: null,
  shortcutsDialogOpen: false,
  copiedMessageId: null,
  sidebarCollapsed: false,
  selectedModel: '',
  selectedThreadIds: new Set<string>(),
  isSelectMode: false,
  // Streaming state
  isStreaming: false,
  streamingContent: '',
  streamingMessageId: null,
  streamingCitations: [],
  streamingDiagnosticsTraceId: null,
  isRetrievingRag: false,
};

// Module-level abort controller (outside Immer state to avoid proxy issues)
let _activeAbortController: AbortController | null = null;

// ============================================================================
// Store
// ============================================================================

export const useChatStore = create<ChatStore>()(
  persist(
    immer((set, get) => ({
      ...initialState,

      // ========================================================================
      // Selection Actions
      // ========================================================================

      setCurrentWorkspace: (workspaceId) => {
        set((state) => {
          state.currentWorkspaceId = workspaceId;
          // Clear downstream selections when workspace changes
          state.currentConversationId = null;
          state.currentThreadId = null;
        });

        // Load conversations for new workspace
        if (workspaceId) {
          get().loadConversations(workspaceId);
        }
      },

      setCurrentConversation: (conversationId) => {
        set((state) => {
          state.currentConversationId = conversationId;
          // Clear thread selection when conversation changes
          state.currentThreadId = null;
        });

        // Load threads for new conversation
        if (conversationId) {
          get().loadThreads(conversationId);
        }
      },

      setCurrentThread: (threadId) => {
        set((state) => {
          state.currentThreadId = threadId;
        });

        // Load messages for new thread
        if (threadId) {
          get().loadMessages(threadId);
        }
      },

      // The project binding lives on the thread row (source_project_id), not
      // in the URL — keep the store copy in sync after a bind/unbind so the
      // context rail survives thread switches and reloads.
      setThreadProjectBinding: (threadId, projectId) => {
        set((state) => {
          for (const list of Object.values(state.threads)) {
            const t = list.find((x) => x.id === threadId);
            if (t) {
              t.source_project_id = projectId;
              break;
            }
          }
        });
      },

      getThreadById: (threadId) => {
        if (!threadId) return undefined;
        for (const list of Object.values(get().threads)) {
          const t = list.find((x) => x.id === threadId);
          if (t) return t;
        }
        return undefined;
      },

      // ========================================================================
      // Workspace Actions
      // ========================================================================

      loadWorkspaces: async () => {
        set((state) => {
          state.isLoadingWorkspaces = true;
          state.error = null;
        });

        try {
          const workspaces = await workspaceService.listWorkspaces();
          set((state) => {
            state.workspaces = workspaces;
            state.isLoadingWorkspaces = false;
          });
        } catch (error) {
          console.error('[ChatStore] Error loading workspaces:', error);
          set((state) => {
            state.error = 'Failed to load workspaces';
            state.isLoadingWorkspaces = false;
          });
        }
      },

      createWorkspace: async (data) => {
        try {
          const workspace = await workspaceService.createWorkspace(data);
          set((state) => {
            state.workspaces.unshift(workspace);
          });
          return workspace;
        } catch (error) {
          console.error('[ChatStore] Error creating workspace:', error);
          set((state) => {
            state.error = 'Failed to create workspace';
          });
          return null;
        }
      },

      updateWorkspace: async (id, data) => {
        try {
          const workspace = await workspaceService.updateWorkspace(id, data);
          set((state) => {
            const index = state.workspaces.findIndex((w) => w.id === id);
            if (index !== -1) {
              state.workspaces[index] = workspace;
            }
          });
          return workspace;
        } catch (error) {
          console.error('[ChatStore] Error updating workspace:', error);
          set((state) => {
            state.error = 'Failed to update workspace';
          });
          return null;
        }
      },

      deleteWorkspace: async (id) => {
        try {
          await workspaceService.deleteWorkspace(id);
          set((state) => {
            state.workspaces = state.workspaces.filter((w) => w.id !== id);
            if (state.currentWorkspaceId === id) {
              state.currentWorkspaceId = null;
              state.currentConversationId = null;
              state.currentThreadId = null;
            }
          });
          return true;
        } catch (error) {
          console.error('[ChatStore] Error deleting workspace:', error);
          set((state) => {
            state.error = 'Failed to delete workspace';
          });
          return false;
        }
      },

      // ========================================================================
      // Conversation Actions
      // ========================================================================

      loadConversations: async (workspaceId) => {
        set((state) => {
          state.isLoadingConversations = true;
          state.error = null;
        });

        try {
          const response =
            await workspaceService.listConversations(workspaceId);
          set((state) => {
            state.conversations[workspaceId] = response.conversations;
            // Populate reverse index for O(1) lookup (GOO-86)
            for (const conv of response.conversations) {
              state.conversationToWorkspace[conv.id] = workspaceId;
            }
            state.isLoadingConversations = false;
          });
        } catch (error: any) {
          console.error('[ChatStore] Error loading conversations:', error);

          // Handle 404 - workspace not found (stale data)
          if (error?.response?.status === 404) {
            console.warn(
              '[ChatStore] Workspace not found (404) - clearing stale data'
            );
            const result = handleStaleDataRecovery(
              get,
              set,
              'loadConversations',
              {
                clearWorkspaces: true,
                loadingKey: 'isLoadingConversations',
              }
            );
            if (result.shouldProceed) {
              result.triggerReinit();
            }
            return;
          }

          set((state) => {
            state.error = 'Failed to load conversations';
            state.isLoadingConversations = false;
          });
        }
      },

      createConversation: async (data) => {
        try {
          const conversation = await workspaceService.createConversation(data);
          set((state) => {
            const workspaceId = data.workspace_id;
            if (!state.conversations[workspaceId]) {
              state.conversations[workspaceId] = [];
            }
            state.conversations[workspaceId].unshift(conversation);
            // Populate reverse index (GOO-86)
            state.conversationToWorkspace[conversation.id] = workspaceId;
          });
          return conversation;
        } catch (error: any) {
          console.error('[ChatStore] Error creating conversation:', error);

          // Handle 404 - workspace not found (stale data)
          if (error?.response?.status === 404) {
            console.warn(
              '[ChatStore] Workspace not found (404) while creating conversation - clearing stale data'
            );
            const result = handleStaleDataRecovery(
              get,
              set,
              'createConversation',
              {
                clearWorkspaces: true,
              }
            );
            if (result.shouldProceed) {
              result.triggerReinit();
            }
            return null;
          }

          set((state) => {
            state.error = 'Failed to create conversation';
          });
          return null;
        }
      },

      updateConversation: async (id, data) => {
        try {
          const conversation = await workspaceService.updateConversation(
            id,
            data
          );
          set((state) => {
            const workspaceId = conversation.workspace_id;
            const convs = state.conversations[workspaceId] || [];
            const index = convs.findIndex((c) => c.id === id);
            if (index !== -1) {
              state.conversations[workspaceId][index] = conversation;
            }
          });
          return conversation;
        } catch (error) {
          console.error('[ChatStore] Error updating conversation:', error);
          set((state) => {
            state.error = 'Failed to update conversation';
          });
          return null;
        }
      },

      deleteConversation: async (id) => {
        try {
          await workspaceService.deleteConversation(id);
          set((state) => {
            // Use O(1) reverse index lookup (GOO-86)
            removeItemFromRecord(
              state.conversations,
              id,
              state.conversationToWorkspace
            );
            if (state.currentConversationId === id) {
              state.currentConversationId = null;
              state.currentThreadId = null;
            }
          });
          return true;
        } catch (error) {
          console.error('[ChatStore] Error deleting conversation:', error);
          set((state) => {
            state.error = 'Failed to delete conversation';
          });
          return false;
        }
      },

      // ========================================================================
      // Thread Actions
      // ========================================================================

      loadThreads: async (conversationId) => {
        set((state) => {
          state.isLoadingThreads = true;
          state.error = null;
        });

        try {
          console.log(
            '[ChatStore] Loading threads for conversation:',
            conversationId
          );
          const response = await workspaceService.listThreads(conversationId);
          console.log(
            '[ChatStore] Loaded threads:',
            response.threads.length,
            response.threads
          );
          set((state) => {
            state.threads[conversationId] = response.threads;
            // Populate reverse index for O(1) lookup (GOO-86)
            for (const thread of response.threads) {
              state.threadToConversation[thread.id] = conversationId;
            }
            state.isLoadingThreads = false;
          });
        } catch (error: any) {
          console.error('[ChatStore] Error loading threads:', error);

          // Handle 404 - conversation not found (stale data)
          if (error?.response?.status === 404) {
            console.warn(
              '[ChatStore] Conversation not found (404) - clearing stale data'
            );
            // Clear workspaces for consistency with loadConversations since we're triggering full reinit
            const result = handleStaleDataRecovery(get, set, 'loadThreads', {
              clearWorkspaces: true,
              loadingKey: 'isLoadingThreads',
            });
            if (result.shouldProceed) {
              result.triggerReinit();
            }
            return;
          }

          set((state) => {
            state.error = 'Failed to load threads';
            state.isLoadingThreads = false;
          });
        }
      },

      createThread: async (data) => {
        try {
          const thread = await workspaceService.createThread(data);
          set((state) => {
            const conversationId = data.conversation_id;
            if (!state.threads[conversationId]) {
              state.threads[conversationId] = [];
            }
            state.threads[conversationId].unshift(thread);
            // Populate reverse index (GOO-86)
            state.threadToConversation[thread.id] = conversationId;
          });
          return thread;
        } catch (error) {
          console.error('[ChatStore] Error creating thread:', error);
          set((state) => {
            state.error = 'Failed to create thread';
          });
          return null;
        }
      },

      updateThread: async (id, data) => {
        try {
          const thread = await workspaceService.updateThread(id, data);
          set((state) => {
            const conversationId = thread.conversation_id;
            const threads = state.threads[conversationId] || [];
            const index = threads.findIndex((t) => t.id === id);
            if (index !== -1) {
              state.threads[conversationId][index] = thread;
            }
          });
          return thread;
        } catch (error) {
          console.error('[ChatStore] Error updating thread:', error);
          set((state) => {
            state.error = 'Failed to update thread';
          });
          return null;
        }
      },

      deleteThread: async (id) => {
        try {
          await workspaceService.deleteThread(id);
          set((state) => {
            // Use O(1) reverse index lookup (GOO-86)
            removeItemFromRecord(state.threads, id, state.threadToConversation);
            if (state.currentThreadId === id) {
              state.currentThreadId = null;
            }
          });
          return true;
        } catch (error) {
          console.error('[ChatStore] Error deleting thread:', error);
          set((state) => {
            state.error = 'Failed to delete thread';
          });
          return false;
        }
      },

      resolveThread: async (id) => {
        return get().updateThread(id, { status: ThreadStatus.RESOLVED });
      },

      reopenThread: async (id) => {
        return get().updateThread(id, { status: ThreadStatus.ACTIVE });
      },

      // ========================================================================
      // Bulk Thread Actions
      // ========================================================================

      toggleSelectMode: () => {
        set((state) => {
          state.isSelectMode = !state.isSelectMode;
          if (!state.isSelectMode) {
            state.selectedThreadIds = new Set();
          }
        });
      },

      toggleThreadSelection: (threadId) => {
        set((state) => {
          const newSet = new Set(state.selectedThreadIds);
          if (newSet.has(threadId)) {
            newSet.delete(threadId);
          } else {
            newSet.add(threadId);
          }
          state.selectedThreadIds = newSet;
        });
      },

      selectAllThreads: (threadIds) => {
        set((state) => {
          if (threadIds) {
            state.selectedThreadIds = new Set(threadIds);
          } else {
            const conversationId = state.currentConversationId;
            if (!conversationId) return;
            const threads = state.threads[conversationId] || [];
            state.selectedThreadIds = new Set(threads.map((t) => t.id));
          }
        });
      },

      clearSelection: () => {
        set((state) => {
          state.selectedThreadIds = new Set();
        });
      },

      bulkResolveThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await workspaceService.bulkResolveThreads(threadIds);

          // Update local state for successful threads
          set((state) => {
            for (const result of response.results) {
              if (result.success && result.thread) {
                // Use O(1) reverse index lookup (GOO-86)
                updateItemInRecord(
                  state.threads,
                  result.thread_id,
                  result.thread,
                  state.threadToConversation
                );
              }
            }
            state.selectedThreadIds = new Set();
            state.isSelectMode = false;
          });

          return response;
        } catch (error) {
          console.error('[ChatStore] Error bulk resolving threads:', error);
          set((state) => {
            state.error = 'Failed to resolve threads';
          });
          return null;
        }
      },

      bulkArchiveThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await workspaceService.bulkArchiveThreads(threadIds);

          set((state) => {
            for (const result of response.results) {
              if (result.success && result.thread) {
                // Use O(1) reverse index lookup (GOO-86)
                updateItemInRecord(
                  state.threads,
                  result.thread_id,
                  result.thread,
                  state.threadToConversation
                );
              }
            }
            state.selectedThreadIds = new Set();
            state.isSelectMode = false;
          });

          return response;
        } catch (error) {
          console.error('[ChatStore] Error bulk archiving threads:', error);
          set((state) => {
            state.error = 'Failed to archive threads';
          });
          return null;
        }
      },

      bulkSummarizeThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response =
            await workspaceService.bulkSummarizeThreads(threadIds);

          // Summarization is async, so we just clear selection and wait for WebSocket updates
          // or return the response so the UI can show a toast
          set((state) => {
            state.selectedThreadIds = new Set();
            state.isSelectMode = false;
          });

          return response;
        } catch (error) {
          console.error('[ChatStore] Error bulk summarizing threads:', error);
          set((state) => {
            state.error = 'Failed to summarize threads';
          });
          return null;
        }
      },

      bulkDeleteThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await workspaceService.bulkDeleteThreads(threadIds);

          set((state) => {
            for (const result of response.results) {
              if (result.success) {
                // Use O(1) reverse index lookup + cleanup (GOO-86)
                removeItemFromRecord(
                  state.threads,
                  result.thread_id,
                  state.threadToConversation
                );
              }
            }

            // Clear current thread if it was deleted
            if (
              state.currentThreadId &&
              threadIds.includes(state.currentThreadId)
            ) {
              state.currentThreadId = null;
            }

            state.selectedThreadIds = new Set();
            state.isSelectMode = false;
          });

          return response;
        } catch (error) {
          console.error('[ChatStore] Error bulk deleting threads:', error);
          set((state) => {
            state.error = 'Failed to delete threads';
          });
          return null;
        }
      },

      // ========================================================================
      // Message Actions
      // ========================================================================

      loadMessages: async (threadId) => {
        set((state) => {
          state.isLoadingMessages = true;
          state.error = null;
        });

        try {
          const response = await workspaceService.listMessages(threadId);
          set((state) => {
            state.messages[threadId] = response.messages;
            // Populate reverse index for O(1) lookup (GOO-86)
            for (const msg of response.messages) {
              state.messageToThread[msg.id] = threadId;
            }

            // Evict oldest cached threads when exceeding the cap (FIFO by key insertion order)
            const threadKeys = Object.keys(state.messages);
            if (threadKeys.length > MAX_CACHED_THREADS) {
              const toEvict = threadKeys.slice(
                0,
                threadKeys.length - MAX_CACHED_THREADS
              );
              for (const key of toEvict) {
                // Clean up reverse index entries for evicted messages
                for (const msg of state.messages[key] || []) {
                  delete state.messageToThread[msg.id];
                }
                delete state.messages[key];
              }
            }

            state.isLoadingMessages = false;
          });
        } catch (error) {
          console.error('[ChatStore] Error loading messages:', error);
          set((state) => {
            state.error = 'Failed to load messages';
            state.isLoadingMessages = false;
          });
        }
      },

      sendMessage: async (content, threadId) => {
        const state = get();
        const targetThreadId = threadId || state.currentThreadId;

        if (!targetThreadId) {
          console.error('[ChatStore] No thread selected for sending message');
          return null;
        }

        set((state) => {
          state.isSendingMessage = true;
          state.error = null;
        });

        try {
          const message = await workspaceService.createMessage({
            thread_id: targetThreadId,
            content,
          });

          set((state) => {
            if (!state.messages[targetThreadId]) {
              state.messages[targetThreadId] = [];
            }
            state.messages[targetThreadId].push(message);
            // Populate reverse index (GOO-86)
            state.messageToThread[message.id] = targetThreadId;
            state.isSendingMessage = false;
          });

          return message;
        } catch (error) {
          console.error('[ChatStore] Error sending message:', error);
          set((state) => {
            state.error = 'Failed to send message';
            state.isSendingMessage = false;
          });
          return null;
        }
      },

      // Add message directly to store without API call
      // Used when page.tsx saves messages with citations through its own flow
      addMessageToStore: (threadId, message) => {
        set((state) => {
          if (!state.messages[threadId]) {
            state.messages[threadId] = [];
          }
          // Check if message already exists to prevent duplicates
          const existingIndex = state.messages[threadId].findIndex(
            (m) => m.id === message.id
          );
          if (existingIndex === -1) {
            state.messages[threadId].push(message);
            state.messageToThread[message.id] = threadId;
            console.log(
              '[ChatStore] Added message to store:',
              message.id,
              'with',
              message.citations?.length || 0,
              'citations'
            );
          } else {
            // Update existing message (e.g., when citations are added later)
            state.messages[threadId][existingIndex] = message;
            console.log(
              '[ChatStore] Updated message in store:',
              message.id,
              'with',
              message.citations?.length || 0,
              'citations'
            );
          }
        });
      },

      updateMessageFeedback: async (id, data) => {
        try {
          const message = await workspaceService.updateMessage(id, data);
          set((state) => {
            const threadId = message.thread_id;
            const messages = state.messages[threadId] || [];
            const index = messages.findIndex((m) => m.id === id);
            if (index !== -1) {
              state.messages[threadId][index] = message;
            }
          });
          return message;
        } catch (error) {
          console.error('[ChatStore] Error updating message feedback:', error);
          set((state) => {
            state.error = 'Failed to update message feedback';
          });
          return null;
        }
      },

      deleteMessage: async (id) => {
        try {
          await workspaceService.deleteMessage(id);
          set((state) => {
            // Use O(1) reverse index lookup (GOO-86)
            removeItemFromRecord(state.messages, id, state.messageToThread);
          });
          return true;
        } catch (error) {
          console.error('[ChatStore] Error deleting message:', error);
          set((state) => {
            state.error = 'Failed to delete message';
          });
          return false;
        }
      },

      clearThread: (threadId) => {
        set((state) => {
          // Clean up reverse index entries for evicted messages
          for (const msg of state.messages[threadId] || []) {
            delete state.messageToThread[msg.id];
          }
          delete state.messages[threadId];
        });
      },

      // ========================================================================
      // UI Actions
      // ========================================================================

      setShortcutsDialogOpen: (open) => {
        set((state) => {
          state.shortcutsDialogOpen = open;
        });
      },

      setCopiedMessageId: (id) => {
        set((state) => {
          state.copiedMessageId = id;
        });
      },

      setSidebarCollapsed: (collapsed) => {
        set((state) => {
          state.sidebarCollapsed = collapsed;
        });
      },

      setSelectedModel: (model) => {
        set((state) => {
          state.selectedModel = model;
        });
      },

      // ========================================================================
      // Streaming Actions
      // ========================================================================

      /**
       * @deprecated Orphaned v2 streaming path. The active chat page uses
       * `agentChatService.streamMessage` directly against `/api/v1/agent/stream`
       * (see `app/(dashboard)/chat/page.tsx`). This action is kept only so the
       * store interface and its existing unit tests stay intact; it has no UI
       * callers. Remove together with `services/streamingService.ts` in a
       * dedicated cleanup PR. Do not extend.
       */
      streamMessage: async (content, threadId, useRag = true) => {
        const state = get();
        const targetThreadId = threadId || state.currentThreadId;

        if (!targetThreadId) {
          console.error('[ChatStore] No thread selected for streaming message');
          return;
        }

        const controller = new AbortController();
        _activeAbortController = controller;

        set((state) => {
          state.isStreaming = true;
          state.streamingContent = '';
          state.streamingMessageId = null;
          state.streamingCitations = [];
          state.streamingDiagnosticsTraceId = null;
          state.error = null;
        });

        try {
          const { streamChatMessage } =
            await import('@/services/streamingService');

          for await (const event of streamChatMessage(
            targetThreadId,
            content,
            { useRag },
            controller.signal
          )) {
            switch (event.type) {
              case 'message_start':
                set((state) => {
                  state.streamingMessageId =
                    (event.data.message_id as string) ?? null;
                });
                break;

              case 'rag_context':
                set((state) => {
                  state.streamingCitations =
                    (event.data.citations as Array<Record<string, unknown>>) ??
                    [];
                  state.streamingDiagnosticsTraceId =
                    (event.data.diagnostics_trace_id as string) ?? null;
                });
                break;

              case 'token':
                set((state) => {
                  state.streamingContent +=
                    (event.data.content as string) ?? '';
                });
                break;

              case 'message_done':
                await get().loadMessages(targetThreadId);
                break;

              case 'error':
                set((state) => {
                  state.error =
                    (event.data.message as string) ??
                    'An error occurred during streaming';
                });
                break;
            }
          }
        } catch (err: any) {
          // Silently catch AbortError (user clicked stop)
          if (err?.name !== 'AbortError') {
            console.error('[ChatStore] Error streaming message:', err);
            set((state) => {
              state.error = 'Failed to stream message';
            });
          }
          // On error/abort, clear streaming state immediately.
          // (For normal completion, the caller — handleSubmit — clears
          // streaming state AFTER syncing local messages to avoid a flash
          // where the virtual streaming message disappears before the
          // final messages are displayed.)
          set((state) => {
            state.isStreaming = false;
            state.streamingContent = '';
            state.streamingMessageId = null;
            state.streamingCitations = [];
            state.streamingDiagnosticsTraceId = null;
          });
          _activeAbortController = null;
        } finally {
          _activeAbortController = null;
        }
      },

      stopStreaming: () => {
        if (_activeAbortController) {
          _activeAbortController.abort();
          _activeAbortController = null;
        }
        set((state) => {
          state.isStreaming = false;
          state.streamingContent = '';
          state.streamingMessageId = null;
          state.streamingCitations = [];
          state.streamingDiagnosticsTraceId = null;
          state.isRetrievingRag = false;
        });
      },

      // ========================================================================
      // Utility Actions
      // ========================================================================

      clearError: () => {
        set((state) => {
          state.error = null;
        });
      },

      reset: () => {
        set(initialState);
      },

      initializeDefaultWorkspace: async () => {
        try {
          console.log('[ChatStore] Initializing default workspace...');
          const { currentWorkspaceId } = get();
          const workspace =
            await workspaceService.getOrCreateDefaultWorkspace();

          // Keep local workspace list in sync with bootstrap result.
          set((state) => {
            if (!state.workspaces.some((w) => w.id === workspace.id)) {
              state.workspaces.unshift(workspace);
            }
          });

          // Clear stale IDs if current workspace no longer exists.
          if (currentWorkspaceId && currentWorkspaceId !== workspace.id) {
            console.warn(
              '[ChatStore] Clearing stale workspace ID:',
              currentWorkspaceId
            );
            set((s) => {
              s.currentWorkspaceId = null;
              s.currentConversationId = null;
              s.currentThreadId = null;
            });
          }

          console.log(
            '[ChatStore] Using workspace:',
            workspace.id,
            workspace.name
          );

          // Set current workspace (this will trigger loadConversations)
          get().setCurrentWorkspace(workspace.id);

          // Reset retry counter on successful initialization
          set((s) => {
            s.reinitRetryCount = 0;
          });
        } catch (error) {
          console.error(
            '[ChatStore] Error initializing default workspace:',
            error
          );
          set((state) => {
            state.error = 'Failed to initialize workspace';
          });
        }
      },
    })),
    {
      name: 'chat-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Only persist these fields
        currentWorkspaceId: state.currentWorkspaceId,
        currentConversationId: state.currentConversationId,
        currentThreadId: state.currentThreadId,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
      onRehydrateStorage: () => () => {
        // Reset streaming state on rehydration to prevent stale UI
        _activeAbortController = null;
      },
    }
  )
);

// ============================================================================
// Selectors (for performance optimization)
// ============================================================================

export const selectCurrentWorkspace = (state: ChatStore) =>
  state.workspaces.find((w) => w.id === state.currentWorkspaceId) || null;

export const selectCurrentConversation = (state: ChatStore) => {
  if (!state.currentWorkspaceId || !state.currentConversationId) return null;
  const conversations = state.conversations[state.currentWorkspaceId] || [];
  return (
    conversations.find((c) => c.id === state.currentConversationId) || null
  );
};

export const selectCurrentThread = (state: ChatStore) => {
  if (!state.currentConversationId || !state.currentThreadId) return null;
  const threads = state.threads[state.currentConversationId] || [];
  return threads.find((t) => t.id === state.currentThreadId) || null;
};

export const selectCurrentMessages = (state: ChatStore) => {
  if (!state.currentThreadId) return [];
  return state.messages[state.currentThreadId] || [];
};

export const selectConversationsForCurrentWorkspace = (state: ChatStore) => {
  if (!state.currentWorkspaceId) return [];
  return state.conversations[state.currentWorkspaceId] || [];
};

export const selectThreadsForCurrentConversation = (state: ChatStore) => {
  if (!state.currentConversationId) return [];
  return state.threads[state.currentConversationId] || [];
};

export default useChatStore;
