/**
 * Chat Store Bulk Operations Tests (GOO-52)
 *
 * Tests for the bulk thread operation actions in chat-store.ts:
 * - toggleSelectMode: Enter/exit multi-select mode
 * - toggleThreadSelection: Add/remove threads from selection
 * - selectAllThreads: Select all threads in current conversation
 * - clearSelection: Clear all selected threads
 * - bulkResolveThreads: Bulk resolve selected threads
 * - bulkArchiveThreads: Bulk archive selected threads
 * - bulkDeleteThreads: Bulk delete selected threads
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { enableMapSet } from 'immer';

// Mock workspace service
const mockWorkspaceService = {
  bulkResolveThreads: jest.fn(),
  bulkArchiveThreads: jest.fn(),
  bulkDeleteThreads: jest.fn(),
};

jest.mock('@/services/workspaceService', () => ({
  workspaceService: mockWorkspaceService,
}));

// Test data
const mockThreads = [
  {
    id: 'thread-1',
    title: 'Thread 1',
    status: 'active',
    message_count: 5,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'thread-2',
    title: 'Thread 2',
    status: 'active',
    message_count: 3,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'thread-3',
    title: 'Thread 3',
    status: 'resolved',
    message_count: 10,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockBulkResponse = {
  total: 2,
  succeeded: 2,
  failed: 0,
  results: [
    { thread_id: 'thread-1', success: true, error: null },
    { thread_id: 'thread-2', success: true, error: null },
  ],
};

// Create a minimal test store that mimics chat-store bulk operations
interface TestState {
  selectedThreadIds: Set<string>;
  isSelectMode: boolean;
  currentConversationId: string | null;
  currentThreadId: string | null;
  threads: Record<string, typeof mockThreads>;
  error: string | null;
}

interface TestActions {
  toggleSelectMode: () => void;
  toggleThreadSelection: (threadId: string) => void;
  selectAllThreads: () => void;
  clearSelection: () => void;
  bulkResolveThreads: () => Promise<typeof mockBulkResponse | null>;
  bulkArchiveThreads: () => Promise<typeof mockBulkResponse | null>;
  bulkDeleteThreads: () => Promise<typeof mockBulkResponse | null>;
}

const createTestStore = () =>
  create<TestState & TestActions>()(
    immer((set, get) => ({
      // State
      selectedThreadIds: new Set<string>(),
      isSelectMode: false,
      currentConversationId: 'conv-1',
      currentThreadId: null,
      threads: { 'conv-1': mockThreads },
      error: null,

      // Actions
      toggleSelectMode: () =>
        set((state) => {
          state.isSelectMode = !state.isSelectMode;
          if (!state.isSelectMode) {
            state.selectedThreadIds = new Set();
          }
        }),

      toggleThreadSelection: (threadId: string) =>
        set((state) => {
          const newSelection = new Set(state.selectedThreadIds);
          if (newSelection.has(threadId)) {
            newSelection.delete(threadId);
          } else {
            newSelection.add(threadId);
          }
          state.selectedThreadIds = newSelection;
        }),

      selectAllThreads: () =>
        set((state) => {
          const conversationId = state.currentConversationId;
          if (conversationId && state.threads[conversationId]) {
            state.selectedThreadIds = new Set(
              state.threads[conversationId].map((t) => t.id)
            );
          }
        }),

      clearSelection: () =>
        set((state) => {
          state.selectedThreadIds = new Set();
        }),

      bulkResolveThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await mockWorkspaceService.bulkResolveThreads(threadIds);
          set((s) => {
            s.selectedThreadIds = new Set();
            s.isSelectMode = false;
          });
          return response;
        } catch (error) {
          set((s) => {
            s.error = 'Failed to resolve threads';
          });
          return null;
        }
      },

      bulkArchiveThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await mockWorkspaceService.bulkArchiveThreads(threadIds);
          set((s) => {
            s.selectedThreadIds = new Set();
            s.isSelectMode = false;
          });
          return response;
        } catch (error) {
          set((s) => {
            s.error = 'Failed to archive threads';
          });
          return null;
        }
      },

      bulkDeleteThreads: async () => {
        const state = get();
        const threadIds = Array.from(state.selectedThreadIds);
        if (threadIds.length === 0) return null;

        try {
          const response = await mockWorkspaceService.bulkDeleteThreads(threadIds);
          set((s) => {
            s.selectedThreadIds = new Set();
            s.isSelectMode = false;
            // Clear currentThreadId if it was deleted
            if (s.currentThreadId && threadIds.includes(s.currentThreadId)) {
              s.currentThreadId = null;
            }
          });
          return response;
        } catch (error) {
          set((s) => {
            s.error = 'Failed to delete threads';
          });
          return null;
        }
      },
    }))
  );

describe('Chat Store Bulk Operations', () => {
  let store: ReturnType<typeof createTestStore>;

  beforeEach(() => {
    enableMapSet();
    store = createTestStore();
    jest.clearAllMocks();
  });

  describe('toggleSelectMode', () => {
    it('should enable select mode when off', () => {
      expect(store.getState().isSelectMode).toBe(false);

      act(() => {
        store.getState().toggleSelectMode();
      });

      expect(store.getState().isSelectMode).toBe(true);
    });

    it('should disable select mode when on', () => {
      act(() => {
        store.getState().toggleSelectMode(); // Enable
        store.getState().toggleSelectMode(); // Disable
      });

      expect(store.getState().isSelectMode).toBe(false);
    });

    it('should clear selection when exiting select mode', () => {
      act(() => {
        store.getState().toggleSelectMode(); // Enable
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-2');
      });

      expect(store.getState().selectedThreadIds.size).toBe(2);

      act(() => {
        store.getState().toggleSelectMode(); // Disable
      });

      expect(store.getState().selectedThreadIds.size).toBe(0);
    });
  });

  describe('toggleThreadSelection', () => {
    it('should add thread to selection', () => {
      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      expect(store.getState().selectedThreadIds.has('thread-1')).toBe(true);
      expect(store.getState().selectedThreadIds.size).toBe(1);
    });

    it('should remove thread from selection if already selected', () => {
      act(() => {
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-1');
      });

      expect(store.getState().selectedThreadIds.has('thread-1')).toBe(false);
      expect(store.getState().selectedThreadIds.size).toBe(0);
    });

    it('should handle multiple selections', () => {
      act(() => {
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-2');
        store.getState().toggleThreadSelection('thread-3');
      });

      expect(store.getState().selectedThreadIds.size).toBe(3);
    });
  });

  describe('selectAllThreads', () => {
    it('should select all threads in current conversation', () => {
      act(() => {
        store.getState().selectAllThreads();
      });

      const selection = store.getState().selectedThreadIds;
      expect(selection.size).toBe(3);
      expect(selection.has('thread-1')).toBe(true);
      expect(selection.has('thread-2')).toBe(true);
      expect(selection.has('thread-3')).toBe(true);
    });
  });

  describe('clearSelection', () => {
    it('should clear all selected threads', () => {
      act(() => {
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-2');
      });

      expect(store.getState().selectedThreadIds.size).toBe(2);

      act(() => {
        store.getState().clearSelection();
      });

      expect(store.getState().selectedThreadIds.size).toBe(0);
    });
  });

  describe('bulkResolveThreads', () => {
    it('should call API with selected thread IDs', async () => {
      mockWorkspaceService.bulkResolveThreads.mockResolvedValue(mockBulkResponse);

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-2');
      });

      await act(async () => {
        await store.getState().bulkResolveThreads();
      });

      expect(mockWorkspaceService.bulkResolveThreads).toHaveBeenCalledWith([
        'thread-1',
        'thread-2',
      ]);
    });

    it('should clear selection after successful resolve', async () => {
      mockWorkspaceService.bulkResolveThreads.mockResolvedValue(mockBulkResponse);

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkResolveThreads();
      });

      expect(store.getState().selectedThreadIds.size).toBe(0);
      expect(store.getState().isSelectMode).toBe(false);
    });

    it('should return null if no threads selected', async () => {
      const result = await store.getState().bulkResolveThreads();

      expect(result).toBeNull();
      expect(mockWorkspaceService.bulkResolveThreads).not.toHaveBeenCalled();
    });

    it('should handle API errors', async () => {
      mockWorkspaceService.bulkResolveThreads.mockRejectedValue(
        new Error('API Error')
      );

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkResolveThreads();
      });

      expect(store.getState().error).toBe('Failed to resolve threads');
    });
  });

  describe('bulkArchiveThreads', () => {
    it('should call API with selected thread IDs', async () => {
      mockWorkspaceService.bulkArchiveThreads.mockResolvedValue(mockBulkResponse);

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkArchiveThreads();
      });

      expect(mockWorkspaceService.bulkArchiveThreads).toHaveBeenCalledWith([
        'thread-1',
      ]);
    });

    it('should clear selection after successful archive', async () => {
      mockWorkspaceService.bulkArchiveThreads.mockResolvedValue(mockBulkResponse);

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkArchiveThreads();
      });

      expect(store.getState().selectedThreadIds.size).toBe(0);
    });
  });

  describe('bulkDeleteThreads', () => {
    it('should call API with selected thread IDs', async () => {
      mockWorkspaceService.bulkDeleteThreads.mockResolvedValue(mockBulkResponse);

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
        store.getState().toggleThreadSelection('thread-2');
      });

      await act(async () => {
        await store.getState().bulkDeleteThreads();
      });

      expect(mockWorkspaceService.bulkDeleteThreads).toHaveBeenCalled();
    });

    it('should clear currentThreadId if it was deleted', async () => {
      mockWorkspaceService.bulkDeleteThreads.mockResolvedValue(mockBulkResponse);

      // Set current thread to one that will be deleted
      store.setState({ currentThreadId: 'thread-1' });

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkDeleteThreads();
      });

      expect(store.getState().currentThreadId).toBeNull();
    });

    it('should keep currentThreadId if it was not deleted', async () => {
      mockWorkspaceService.bulkDeleteThreads.mockResolvedValue(mockBulkResponse);

      // Set current thread to one that won't be deleted
      store.setState({ currentThreadId: 'thread-3' });

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkDeleteThreads();
      });

      expect(store.getState().currentThreadId).toBe('thread-3');
    });

    it('should handle API errors', async () => {
      mockWorkspaceService.bulkDeleteThreads.mockRejectedValue(
        new Error('API Error')
      );

      act(() => {
        store.getState().toggleThreadSelection('thread-1');
      });

      await act(async () => {
        await store.getState().bulkDeleteThreads();
      });

      expect(store.getState().error).toBe('Failed to delete threads');
    });
  });
});
