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

// Association rows as the backend actually returns them:
// GET /projects/{id}/documents → {id: <association>, document_id, document:
// {id, title, filename, ...}} — the document is nested, titles are NOT on
// the row itself.
const apiDocuments = {
  documents: [
    {
      id: 'assoc-1',
      project_id: 'p1',
      document_id: 'doc-1',
      sort_order: 0,
      document: {
        id: 'doc-1',
        title: 'EHR-RAGp: Retrieval-Augmented Prototypes',
        filename: 'ehr-ragp.pdf',
        status: 'indexed',
      },
    },
    {
      id: 'assoc-2',
      project_id: 'p1',
      document_id: 'doc-2',
      sort_order: 1,
      document: {
        id: 'doc-2',
        title: null as unknown as string,
        filename: 'untitled-upload.pdf',
        status: 'indexed',
      },
    },
  ],
  total: 2,
};

// Notes come back snake_case (is_pinned) — no camelize layer in api-client.
const apiNotes = {
  notes: [
    {
      id: 'n1',
      project_id: 'p1',
      title: 'Paper notes',
      content: '',
      is_pinned: true,
      created_at: '2026-07-03T00:00:00Z',
      updated_at: '2026-07-03T00:00:00Z',
    },
  ],
  total: 1,
};

const apiDrafts = {
  drafts: [
    {
      id: 'dr1',
      project_id: 'p1',
      version: 2,
      title: 'Draft 1',
      themes: [],
      word_count: 100,
      citation_count: 0,
      is_current: true,
      created_at: '2026-07-03T00:00:00Z',
    },
  ],
  total: 1,
  skip: 0,
  limit: 100,
};

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

  it('flattens nested document rows to {id: documentId, title}', async () => {
    mockedProjectService.listProjectDocuments.mockResolvedValue(apiDocuments);
    mockedProjectService.listProjectNotes.mockResolvedValue(apiNotes);
    mockedProjectService.listDrafts.mockResolvedValue(apiDrafts);
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // id must be the DOCUMENT id, not the association row id.
    expect(result.current.documents?.[0]).toEqual({
      id: 'doc-1',
      title: 'EHR-RAGp: Retrieval-Augmented Prototypes',
    });
  });

  it('falls back to the filename when the document has no title', async () => {
    mockedProjectService.listProjectDocuments.mockResolvedValue(apiDocuments);
    mockedProjectService.listProjectNotes.mockResolvedValue(apiNotes);
    mockedProjectService.listDrafts.mockResolvedValue(apiDrafts);
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.documents?.[1]).toEqual({
      id: 'doc-2',
      title: 'untitled-upload.pdf',
    });
  });

  it('maps snake_case is_pinned to isPinned on notes', async () => {
    mockedProjectService.listProjectDocuments.mockResolvedValue(apiDocuments);
    mockedProjectService.listProjectNotes.mockResolvedValue(apiNotes);
    mockedProjectService.listDrafts.mockResolvedValue(apiDrafts);
    const { result } = renderHook(() => useProjectWorkingFolders('p1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.notes?.[0]).toEqual({
      id: 'n1',
      title: 'Paper notes',
      isPinned: true,
    });
    expect(result.current.drafts?.[0]).toEqual({
      id: 'dr1',
      title: 'Draft 1',
      version: 2,
    });
  });

  it('one failing query does not block the other two', async () => {
    mockedProjectService.listProjectDocuments.mockRejectedValue(
      new Error('boom')
    );
    mockedProjectService.listProjectNotes.mockResolvedValue(apiNotes);
    mockedProjectService.listDrafts.mockResolvedValue({
      drafts: [],
      total: 0,
      skip: 0,
      limit: 100,
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
