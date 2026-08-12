import { useQuery } from '@tanstack/react-query';

import {
  projectService,
  type Draft,
  type ProjectNote,
} from '@/services/projectService';

/**
 * Content fetching for note/draft artifacts. Keys live under
 * ['project', projectId, …] so the existing PROJECT_MUTATING_TOOLS
 * invalidation (useChatStreaming / agentChatStore) refreshes an open
 * note/draft after the agent edits it — no extra wiring. Tenant scoping is
 * inherited from the project endpoints.
 */
export function useNoteArtifact(projectId: string, noteId: string) {
  return useQuery<ProjectNote>({
    queryKey: ['project', projectId, 'note', noteId],
    queryFn: () => projectService.getNote(projectId, noteId),
  });
}

export function useDraftArtifact(projectId: string, draftId: string) {
  return useQuery<Draft>({
    queryKey: ['project', projectId, 'draft', draftId],
    queryFn: () => projectService.getDraft(projectId, draftId),
  });
}
