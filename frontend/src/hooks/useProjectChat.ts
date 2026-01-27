/**
 * useProjectChat Hook
 * Convenience hook for project-specific chat operations with memoization
 *
 * Usage:
 *   const { threads, isLoading, error, startChat, linkThread, unlinkThread } = useProjectChat(projectId);
 */

import { useMemo, useCallback } from 'react';
import {
  useProjectChatStore,
  selectProjectThreads,
  selectProjectLoading,
  selectProjectError,
} from '@/store/projectChatStore';
import type {
  StartChatFromProjectRequest,
  LinkThreadRequest,
  SaveThreadToNoteRequest,
} from '@/types/project-chat';

/**
 * Hook for project-specific chat operations
 *
 * @param projectId - Project UUID
 * @returns Memoized selectors and bound actions
 */
export function useProjectChat(projectId: string) {
  const store = useProjectChatStore();

  // Memoized selectors
  const threads = useMemo(
    () => selectProjectThreads(projectId)(store),
    [store.linkedThreads, projectId]
  );

  const isLoading = useMemo(
    () => selectProjectLoading(projectId)(store),
    [
      store.loadingThreads,
      store.startingChat,
      store.linkingThread,
      store.unlinkingThread,
      store.savingToNote,
      projectId,
    ]
  );

  const error = useMemo(
    () => selectProjectError(projectId)(store),
    [store.errors, projectId]
  );

  // Bound actions
  const startChat = useCallback(
    (request: StartChatFromProjectRequest) =>
      store.startChatFromProject(projectId, request),
    [projectId, store.startChatFromProject]
  );

  const linkThread = useCallback(
    (request: LinkThreadRequest) => store.linkThreadToProject(projectId, request),
    [projectId, store.linkThreadToProject]
  );

  const unlinkThread = useCallback(
    (threadId: string) => store.unlinkThreadFromProject(projectId, threadId),
    [projectId, store.unlinkThreadFromProject]
  );

  const saveToNote = useCallback(
    (request: SaveThreadToNoteRequest) =>
      store.saveThreadToNote(projectId, request),
    [projectId, store.saveThreadToNote]
  );

  const refreshThreads = useCallback(
    () => store.fetchProjectThreads(projectId),
    [projectId, store.fetchProjectThreads]
  );

  const clearError = useCallback(
    () => store.clearError(projectId),
    [projectId, store.clearError]
  );

  return {
    // State
    threads,
    isLoading,
    error,

    // Actions
    startChat,
    linkThread,
    unlinkThread,
    saveToNote,
    refreshThreads,
    clearError,
  };
}

export default useProjectChat;
