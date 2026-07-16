'use client';

import { useQuery } from '@tanstack/react-query';
import { projectService } from '@/services/projectService';

export interface WorkingFoldersResult {
  documents: Array<{ id: string; title?: string | null }> | undefined;
  notes: Array<{ id: string; title: string; isPinned?: boolean }> | undefined;
  drafts: Array<{ id: string; title: string; version?: number }> | undefined;
  isLoading: boolean;
  errors: {
    documents?: Error;
    notes?: Error;
    drafts?: Error;
  };
}

export function useProjectWorkingFolders(
  projectId: string | undefined
): WorkingFoldersResult {
  const enabled = Boolean(projectId);

  const docsQ = useQuery({
    queryKey: ['project', projectId, 'documents'],
    queryFn: () =>
      projectService.listProjectDocuments(projectId as string, { limit: 100 }),
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const notesQ = useQuery({
    queryKey: ['project', projectId, 'notes'],
    queryFn: () =>
      projectService.listProjectNotes(projectId as string, { limit: 100 }),
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const draftsQ = useQuery({
    queryKey: ['project', projectId, 'drafts'],
    queryFn: () =>
      projectService.listDrafts(projectId as string, {
        includeContent: false,
        limit: 100,
      }),
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return {
    documents: docsQ.data?.documents ?? (docsQ.isError ? [] : undefined),
    notes: notesQ.data?.notes ?? (notesQ.isError ? [] : undefined),
    drafts: draftsQ.data?.drafts ?? (draftsQ.isError ? [] : undefined),
    isLoading: docsQ.isLoading || notesQ.isLoading || draftsQ.isLoading,
    errors: {
      documents: docsQ.error as Error | undefined,
      notes: notesQ.error as Error | undefined,
      drafts: draftsQ.error as Error | undefined,
    },
  };
}
