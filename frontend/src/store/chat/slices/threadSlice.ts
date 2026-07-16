/**
 * Thread CRUD + bulk thread actions.
 *
 * Split out of chat-store.ts (Task 5.4) with no behavior change. Deleting a
 * thread must also clear its cached messages/pagination/freshness (the
 * message-slice's coupled triple) and abort its in-flight newest-page
 * request — that cross-cutting cleanup lives here because thread deletion
 * owns the "when", even though the fields belong to the message slice.
 */
import { BulkThreadResponse, ThreadCreate, ThreadStatus, ThreadUpdate } from '@/types/workspace';
import type { Thread } from '@/types/workspace';
import { workspaceService } from '@/services/workspaceService';
import type { ChatSliceCreator } from '../types';
import { removeItemFromRecord, updateItemInRecord } from '../recordIndex';
import { abortNewestPageRequest } from '../requestCoordinator';
import { handleStaleDataRecovery } from './workspaceSlice';

export interface ThreadSlice {
  loadThreads: (conversationId: string) => Promise<void>;
  createThread: (data: ThreadCreate) => Promise<Thread | null>;
  updateThread: (id: string, data: ThreadUpdate) => Promise<Thread | null>;
  deleteThread: (id: string) => Promise<boolean>;
  resolveThread: (id: string) => Promise<Thread | null>;
  reopenThread: (id: string) => Promise<Thread | null>;

  toggleSelectMode: () => void;
  toggleThreadSelection: (threadId: string) => void;
  selectAllThreads: (threadIds?: string[]) => void;
  clearSelection: () => void;
  bulkResolveThreads: () => Promise<BulkThreadResponse | null>;
  bulkArchiveThreads: () => Promise<BulkThreadResponse | null>;
  bulkSummarizeThreads: () => Promise<BulkThreadResponse | null>;
  bulkDeleteThreads: () => Promise<BulkThreadResponse | null>;
}

export const createThreadSlice: ChatSliceCreator<ThreadSlice> = (
  set,
  get
) => ({
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
    } catch (error) {
      console.error('[ChatStore] Error loading threads:', error);

      // Handle 404 - conversation not found (stale data)
      const err = error as { response?: { status?: number } };
      if (err?.response?.status === 404) {
        // A late 404 for a conversation the user has already navigated away
        // from must not nuke the (valid) current selection — only recover
        // when the failed load still targets the current conversation.
        if (get().currentConversationId !== conversationId) {
          console.warn(
            '[ChatStore] Ignoring stale 404 for superseded conversation:',
            conversationId
          );
          set((state) => {
            state.isLoadingThreads = false;
          });
          return;
        }
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
      abortNewestPageRequest(id);
      set((state) => {
        // Use O(1) reverse index lookup (GOO-86)
        removeItemFromRecord(state.threads, id, state.threadToConversation);
        for (const message of state.messages[id] || []) {
          delete state.messageToThread[message.id];
        }
        delete state.messages[id];
        delete state.messagePagination[id];
        delete state.messageFreshness[id];
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
      const response = await workspaceService.bulkSummarizeThreads(threadIds);

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
      for (const result of response.results) {
        if (result.success) {
          abortNewestPageRequest(result.thread_id);
        }
      }

      set((state) => {
        for (const result of response.results) {
          if (result.success) {
            // Use O(1) reverse index lookup + cleanup (GOO-86)
            removeItemFromRecord(
              state.threads,
              result.thread_id,
              state.threadToConversation
            );
            for (const message of state.messages[result.thread_id] || []) {
              delete state.messageToThread[message.id];
            }
            delete state.messages[result.thread_id];
            delete state.messagePagination[result.thread_id];
            delete state.messageFreshness[result.thread_id];
          }
        }

        // Clear current thread only if its delete actually SUCCEEDED — a
        // failed delete leaves the thread alive server-side and still
        // validly selected (clearing on requested ids deselected it anyway).
        const deletedIds = new Set(
          response.results
            .filter((result) => result.success)
            .map((result) => result.thread_id)
        );
        if (state.currentThreadId && deletedIds.has(state.currentThreadId)) {
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
});
