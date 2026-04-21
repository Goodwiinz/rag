import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { useProjectWorkingFolders } from '../useProjectWorkingFolders';

jest.mock('@/services/projectService', () => ({
  projectService: {
    listProjectDocuments: jest.fn(),
    listProjectNotes: jest.fn(),
    listDrafts: jest.fn(),
  },
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { projectService } = require('@/services/projectService');

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useProjectWorkingFolders', () => {
  beforeEach(() => jest.clearAllMocks());

  it('returns undefined lists before the queries resolve', () => {
    projectService.listProjectDocuments.mockReturnValue(new Promise(() => {}));
    projectService.listProjectNotes.mockReturnValue(new Promise(() => {}));
    projectService.listDrafts.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    expect(result.current.documents).toBeUndefined();
    expect(result.current.notes).toBeUndefined();
    expect(result.current.drafts).toBeUndefined();
    expect(result.current.isLoading).toBe(true);
  });

  it('returns fetched lists once all queries resolve', async () => {
    projectService.listProjectDocuments.mockResolvedValue({
      documents: [{ id: 'd1', title: 'Doc 1' }],
      total: 1,
    });
    projectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    projectService.listDrafts.mockResolvedValue({
      drafts: [{ id: 'd1', title: 'Draft 1', version: 2 }],
      total: 1,
    });
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toHaveLength(1);
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.drafts).toHaveLength(1);
  });

  it('one failing query does not block the other two', async () => {
    projectService.listProjectDocuments.mockRejectedValue(new Error('boom'));
    projectService.listProjectNotes.mockResolvedValue({
      notes: [{ id: 'n1', title: 'Note 1', isPinned: false }],
      total: 1,
    });
    projectService.listDrafts.mockResolvedValue({
      drafts: [],
      total: 0,
    });
    const { result } = renderHook(
      () => useProjectWorkingFolders('p1'),
      { wrapper }
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents).toEqual([]); // falls back to empty
    expect(result.current.notes).toHaveLength(1);
    expect(result.current.errors.documents).toBeTruthy();
  });

  it('does not fetch when projectId is undefined', () => {
    renderHook(() => useProjectWorkingFolders(undefined), { wrapper });
    expect(projectService.listProjectDocuments).not.toHaveBeenCalled();
    expect(projectService.listProjectNotes).not.toHaveBeenCalled();
    expect(projectService.listDrafts).not.toHaveBeenCalled();
  });
});
