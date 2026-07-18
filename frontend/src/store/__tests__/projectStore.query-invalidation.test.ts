/**
 * Dual-cache reconciliation (docs/engineering/frontend.md, "Legacy
 * server-state stores"): projectStore document/note mutations must
 * invalidate the context rail's Query copies (['project', id, 'documents' |
 * 'notes']) or the rail serves stale lists for its 5-minute staleTime.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mocked } from 'vitest';
import type { QueryClient } from '@tanstack/react-query';
import { useProjectStore } from '../projectStore';
import { setAppQueryClient } from '@/lib/query-client';
import { projectService } from '@/services/projectService';

vi.mock('@/services/projectService', () => ({
  projectService: {
    addDocumentToProject: vi.fn(),
    removeDocumentFromProject: vi.fn(),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    deleteNote: vi.fn(),
    toggleNotePin: vi.fn(),
  },
}));

const mockService = projectService as Mocked<typeof projectService>;

const invalidateQueries = vi.fn().mockResolvedValue(undefined);

describe('projectStore Query-cache invalidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProjectStore.getState().reset();
    setAppQueryClient({ invalidateQueries } as unknown as QueryClient);
  });

  it('invalidates the documents query on add/remove document', async () => {
    mockService.addDocumentToProject.mockResolvedValue({
      id: 'assoc-1',
      document_id: 'd1',
    } as never);
    mockService.removeDocumentFromProject.mockResolvedValue(undefined as never);

    await useProjectStore.getState().addDocument('p1', 'd1');
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['project', 'p1', 'documents'],
    });

    await useProjectStore.getState().removeDocument('p1', 'd1');
    expect(invalidateQueries).toHaveBeenCalledTimes(2);
  });

  it('invalidates the notes query on note create/update/delete/pin', async () => {
    const note = { id: 'n1', title: 'Note' } as never;
    mockService.createNote.mockResolvedValue(note);
    mockService.updateNote.mockResolvedValue(note);
    mockService.deleteNote.mockResolvedValue(undefined as never);
    mockService.toggleNotePin.mockResolvedValue(note);

    const store = useProjectStore.getState();
    await store.createNote('p1', { title: 'Note', content: '' } as never);
    await store.updateNote('p1', 'n1', { title: 'Note 2' } as never);
    await store.deleteNote('p1', 'n1');
    await store.toggleNotePin('p1', 'n1');

    expect(invalidateQueries).toHaveBeenCalledTimes(4);
    for (const call of invalidateQueries.mock.calls) {
      expect(call[0]).toEqual({ queryKey: ['project', 'p1', 'notes'] });
    }
  });

  it('does not invalidate when the mutation fails', async () => {
    mockService.createNote.mockRejectedValue(new Error('boom'));
    await expect(
      useProjectStore.getState().createNote('p1', { title: 'x' } as never)
    ).rejects.toThrow('boom');
    expect(invalidateQueries).not.toHaveBeenCalled();
  });
});
