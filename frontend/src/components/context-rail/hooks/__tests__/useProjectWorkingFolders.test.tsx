import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { useProjectWorkingFolders } from '../useProjectWorkingFolders';
import { projectService } from '@/services/projectService';

vi.mock('@/services/projectService', () => ({
  projectService: {
    listProjectDocuments: vi.fn(),
    listProjectNotes: vi.fn(),
    listDrafts: vi.fn(),
  },
}));

const mockedProjectService = vi.mocked(projectService);

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useProjectWorkingFolders', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns undefined lists before the queries resolve', () => {
    mockedProjectService.listProjectDocuments.mockReturnValue(
      new Promise(() => {})
    );
    mockedProjectService.listProjectNotes.mockReturnValue(
      new Promise(() => {})
    );
    mockedProjectService.listDrafts.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    expect(result.current.documents).toBeUndefined();
    expect(result.current.notes).toBeUndefined();
    expect(result.current.drafts).toBeUndefined();
    expect(result.current.isLoading).toBe(true);
  });

  it('returns fetched lists once all queries resolve', async () => {
    mockedProjectService.listProjectDocuments.mockResolvedValue({
      documents: [{ id: 'd1', title: 'Doc 1' }],
      total: 1,
    });
    mockedProjectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    mockedProjectService.listDrafts.mockResolvedValue({
      drafts: [{ id: 'd1', title: 'Draft 1', version: 2 }],
      total: 1,
    });
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toHaveLength(1);
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.drafts).toHaveLength(1);
  });

  it('one failing query does not block the other two', async () => {
    mockedProjectService.listProjectDocuments.mockRejectedValue(
      new Error('boom')
    );
    mockedProjectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    mockedProjectService.listDrafts.mockResolvedValue({
      drafts: [],
      total: 0,
    });
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toEqual([]); // falls back to empty
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.errors.documents).toBeTruthy();
  });

  it('does not fetch when projectId is undefined', () => {
    renderHook(() => useProjectWorkingFolders(undefined), { wrapper });
    expect(mockedProjectService.listProjectDocuments).not.toHaveBeenCalled();
    expect(mockedProjectService.listProjectNotes).not.toHaveBeenCalled();
    expect(mockedProjectService.listDrafts).not.toHaveBeenCalled();
  });
});
