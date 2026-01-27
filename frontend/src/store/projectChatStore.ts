/**
 * Project-Chat Store - Zustand store for project-chat integration
 * Manages project-thread links with per-project state isolation
 *
 * Architecture:
 * - State keyed by projectId for O(1) lookup
 * - Immer middleware for clean mutation syntax
 * - No persistence (data fetched on-demand)
 * - Per-project loading/error states
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { projectChatService } from '@/services/projectChatService';
import type {
  ProjectThread,
  StartChatFromProjectRequest,
  LinkThreadRequest,
  SaveThreadToNoteRequest,
  StartChatFromProjectResponse,
} from '@/types/project-chat';
import type { NoteResponse } from '@/types/research';

// ============================================================================
// State Interface
// ============================================================================

interface ProjectChatState {
  // Data - keyed by projectId for O(1) lookup
  linkedThreads: Record<string, ProjectThread[]>;

  // Loading states - per-project granularity
  loadingThreads: Record<string, boolean>;
  startingChat: Record<string, boolean>;
  linkingThread: Record<string, boolean>;
  unlinkingThread: Record<string, boolean>;
  savingToNote: Record<string, boolean>;

  // Errors - per-project isolation
  errors: Record<string, string | null>;

  // Actions
  fetchProjectThreads: (projectId: string) => Promise<void>;
  startChatFromProject: (
    projectId: string,
    request: StartChatFromProjectRequest
  ) => Promise<StartChatFromProjectResponse | null>;
  linkThreadToProject: (
    projectId: string,
    request: LinkThreadRequest
  ) => Promise<ProjectThread | null>;
  unlinkThreadFromProject: (projectId: string, threadId: string) => Promise<void>;
  saveThreadToNote: (
    projectId: string,
    request: SaveThreadToNoteRequest
  ) => Promise<NoteResponse | null>;
  clearError: (projectId: string) => void;
  reset: () => void;
}

// ============================================================================
// Initial State
// ============================================================================

const initialState = {
  linkedThreads: {},
  loadingThreads: {},
  startingChat: {},
  linkingThread: {},
  unlinkingThread: {},
  savingToNote: {},
  errors: {},
};

// ============================================================================
// Store Implementation
// ============================================================================

export const useProjectChatStore = create<ProjectChatState>()(
  immer((set, get) => ({
    ...initialState,

    /**
     * Fetch all threads linked to a project
     */
    fetchProjectThreads: async (projectId: string) => {
      // Guard against invalid project IDs
      if (!projectId || projectId === 'undefined') {
        console.warn('[ProjectChatStore] fetchProjectThreads called with invalid projectId:', projectId);
        return;
      }

      set((state) => {
        state.loadingThreads[projectId] = true;
        state.errors[projectId] = null;
      });

      try {
        const response = await projectChatService.listProjectThreads(projectId);

        set((state) => {
          state.linkedThreads[projectId] = response.threads;
          state.loadingThreads[projectId] = false;
        });
      } catch (error: any) {
        console.error('[ProjectChatStore] fetchProjectThreads failed:', error);
        set((state) => {
          state.errors[projectId] = error?.message || 'Failed to fetch threads';
          state.loadingThreads[projectId] = false;
        });
      }
    },

    /**
     * Start a new chat thread from a project with document context
     */
    startChatFromProject: async (
      projectId: string,
      request: StartChatFromProjectRequest
    ) => {
      // Guard against invalid project IDs
      if (!projectId || projectId === 'undefined') {
        console.warn('[ProjectChatStore] startChatFromProject called with invalid projectId:', projectId);
        return null;
      }

      set((state) => {
        state.startingChat[projectId] = true;
        state.errors[projectId] = null;
      });

      try {
        const response = await projectChatService.startChatFromProject(
          projectId,
          request
        );

        set((state) => {
          state.startingChat[projectId] = false;
        });

        // Refresh threads list
        await get().fetchProjectThreads(projectId);

        return response;
      } catch (error: any) {
        console.error('[ProjectChatStore] startChatFromProject failed:', error);
        set((state) => {
          state.errors[projectId] = error?.message || 'Failed to start chat';
          state.startingChat[projectId] = false;
        });
        return null;
      }
    },

    /**
     * Link an existing thread to a project
     */
    linkThreadToProject: async (
      projectId: string,
      request: LinkThreadRequest
    ) => {
      // Guard against invalid project IDs
      if (!projectId || projectId === 'undefined') {
        console.warn('[ProjectChatStore] linkThreadToProject called with invalid projectId:', projectId);
        return null;
      }

      set((state) => {
        state.linkingThread[projectId] = true;
        state.errors[projectId] = null;
      });

      try {
        const response = await projectChatService.linkThreadToProject(
          projectId,
          request
        );

        // Optimistic update - add to local state immediately
        set((state) => {
          if (!state.linkedThreads[projectId]) {
            state.linkedThreads[projectId] = [];
          }
          state.linkedThreads[projectId].unshift(response);
          state.linkingThread[projectId] = false;
        });

        return response;
      } catch (error: any) {
        console.error('[ProjectChatStore] linkThreadToProject failed:', error);
        set((state) => {
          state.errors[projectId] = error?.message || 'Failed to link thread';
          state.linkingThread[projectId] = false;
        });
        return null;
      }
    },

    /**
     * Unlink a thread from a project
     */
    unlinkThreadFromProject: async (projectId: string, threadId: string) => {
      // Guard against invalid project IDs
      if (!projectId || projectId === 'undefined') {
        console.warn('[ProjectChatStore] unlinkThreadFromProject called with invalid projectId:', projectId);
        return;
      }

      set((state) => {
        state.unlinkingThread[projectId] = true;
        state.errors[projectId] = null;
      });

      try {
        await projectChatService.unlinkThreadFromProject(projectId, threadId);

        // Optimistic update - remove from local state immediately
        set((state) => {
          const threads = state.linkedThreads[projectId];
          if (threads) {
            state.linkedThreads[projectId] = threads.filter(
              (t) => t.thread_id !== threadId
            );
          }
          state.unlinkingThread[projectId] = false;
        });
      } catch (error: any) {
        console.error('[ProjectChatStore] unlinkThreadFromProject failed:', error);
        set((state) => {
          state.errors[projectId] = error?.message || 'Failed to unlink thread';
          state.unlinkingThread[projectId] = false;
        });
      }
    },

    /**
     * Save thread content to a project note
     */
    saveThreadToNote: async (
      projectId: string,
      request: SaveThreadToNoteRequest
    ) => {
      // Guard against invalid project IDs
      if (!projectId || projectId === 'undefined') {
        console.warn('[ProjectChatStore] saveThreadToNote called with invalid projectId:', projectId);
        return null;
      }

      set((state) => {
        state.savingToNote[projectId] = true;
        state.errors[projectId] = null;
      });

      try {
        const response = await projectChatService.saveThreadToNote(
          projectId,
          request
        );

        set((state) => {
          state.savingToNote[projectId] = false;
        });

        return response;
      } catch (error: any) {
        console.error('[ProjectChatStore] saveThreadToNote failed:', error);
        set((state) => {
          state.errors[projectId] = error?.message || 'Failed to save thread to note';
          state.savingToNote[projectId] = false;
        });
        return null;
      }
    },

    /**
     * Clear error state for a project
     */
    clearError: (projectId: string) => {
      set((state) => {
        state.errors[projectId] = null;
      });
    },

    /**
     * Reset entire store to initial state
     */
    reset: () => {
      set(initialState);
    },
  }))
);

// ============================================================================
// Selectors (Optional convenience exports)
// ============================================================================

/**
 * Get threads for a specific project
 */
export const selectProjectThreads = (projectId: string) => (state: ProjectChatState) =>
  state.linkedThreads[projectId] || [];

/**
 * Get loading state for a specific project
 */
export const selectProjectLoading = (projectId: string) => (state: ProjectChatState) =>
  state.loadingThreads[projectId] ||
  state.startingChat[projectId] ||
  state.linkingThread[projectId] ||
  state.unlinkingThread[projectId] ||
  state.savingToNote[projectId] ||
  false;

/**
 * Get error state for a specific project
 */
export const selectProjectError = (projectId: string) => (state: ProjectChatState) =>
  state.errors[projectId] || null;

export default useProjectChatStore;
