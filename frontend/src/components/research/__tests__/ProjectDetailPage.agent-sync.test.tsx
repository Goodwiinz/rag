import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@/test/test-utils';
import { useAgentChatStore } from '@/store/agentChatStore';
import ProjectDetailPage from '../../../../app/(dashboard)/projects/[id]/page';
import { useProjectStore } from '@/store/projectStore';
import { projectService } from '@/services/projectService';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1' }),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

vi.mock('@/store/projectStore', () => ({
  useProjectStore: vi.fn(),
}));

vi.mock('@/services/projectService', () => ({
  projectService: {
    listDrafts: vi.fn(),
    getDraft: vi.fn(),
    compareDrafts: vi.fn(),
    cancelGeneration: vi.fn(),
    generateDraft: vi.fn(),
    getGenerationStatus: vi.fn(),
    downloadDraftExport: vi.fn(),
  },
}));

vi.mock('@/components/research/ProjectHeader', () => ({
  ProjectHeader: ({ project }: { project: { name: string } }) => (
    <div>{project.name}</div>
  ),
}));
vi.mock('@/components/research/DocumentList', () => ({
  DocumentList: () => <div>Documents Content</div>,
}));
vi.mock('@/components/research/DraftGenerator', () => ({
  DraftGenerator: () => <div>Draft Generator</div>,
}));
vi.mock('@/components/research/DraftViewer', () => ({
  DraftViewer: ({ draft }: { draft: { title: string } }) => (
    <div>{draft.title}</div>
  ),
}));
vi.mock('@/components/research/DraftGenerationProgress', () => ({
  DraftGenerationProgress: () => <div>Draft Progress</div>,
}));
vi.mock('@/components/research/DraftComparison', () => ({
  DraftComparison: () => <div>Draft Comparison</div>,
}));
vi.mock('@/components/research/DraftExportModal', () => ({
  DraftExportModal: () => null,
}));
vi.mock('@/components/research/ProjectChatTab', () => ({
  ProjectChatTab: () => <div>Project Chat</div>,
}));
vi.mock('@/components/research/ExtractionMatrix', () => ({
  ExtractionMatrix: () => <div>Matrix</div>,
}));
vi.mock('@/components/research/ResearchPipeline', () => ({
  ResearchPipeline: () => <div>Pipeline</div>,
}));
vi.mock('@/components/research/NoteEditor', () => ({
  NoteEditor: () => null,
}));
vi.mock('@/components/research/NoteList', () => ({
  NoteList: () => <div>Notes</div>,
}));
vi.mock('@/components/upload', () => ({
  DocumentUploadWizard: () => null,
}));

const mockUseProjectStore = useProjectStore as unknown as Mock;
const mockProjectService = vi.mocked(projectService);

const mockFetchProject = vi.fn().mockResolvedValue(undefined);
const mockFetchProjectDocuments = vi.fn().mockResolvedValue(undefined);
const mockFetchProjectNotes = vi.fn().mockResolvedValue(undefined);
const mockFetchBibliography = vi.fn().mockResolvedValue(undefined);
const mockDownloadBibliography = vi.fn().mockResolvedValue(undefined);
const mockRemoveDocument = vi.fn().mockResolvedValue(undefined);
const mockCreateNote = vi.fn().mockResolvedValue(undefined);
const mockUpdateNote = vi.fn().mockResolvedValue(undefined);
const mockDeleteNote = vi.fn().mockResolvedValue(undefined);
const mockToggleNotePin = vi.fn().mockResolvedValue(undefined);
const mockClearError = vi.fn();

describe('ProjectDetailPage agent sync', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    vi.clearAllMocks();
    // Vitest config has `restoreMocks: true`, which resets `.mockResolvedValue`
    // set on bare `vi.fn()` between tests. Re-arm the resolutions here so the
    // page component's `fetchProject(...).then(...)` chain doesn't see undefined.
    mockFetchProject.mockResolvedValue(undefined);
    mockFetchProjectDocuments.mockResolvedValue(undefined);
    mockFetchProjectNotes.mockResolvedValue(undefined);
    mockFetchBibliography.mockResolvedValue(undefined);
    mockDownloadBibliography.mockResolvedValue(undefined);
    mockRemoveDocument.mockResolvedValue(undefined);
    mockCreateNote.mockResolvedValue(undefined);
    mockUpdateNote.mockResolvedValue(undefined);
    mockDeleteNote.mockResolvedValue(undefined);
    mockToggleNotePin.mockResolvedValue(undefined);

    mockUseProjectStore.mockReturnValue({
      currentProject: {
        id: 'proj-1',
        name: 'Project One',
        workspace_id: 'ws-1',
        created_at: '2026-03-25T00:00:00Z',
        updated_at: '2026-03-25T00:00:00Z',
      },
      projectDocuments: [],
      projectNotes: [],
      bibliography: null,
      loading: false,
      mutating: false,
      documentsLoading: false,
      notesLoading: false,
      error: null,
      fetchProject: mockFetchProject,
      fetchProjectDocuments: mockFetchProjectDocuments,
      fetchProjectNotes: mockFetchProjectNotes,
      removeDocument: mockRemoveDocument,
      createNote: mockCreateNote,
      updateNote: mockUpdateNote,
      deleteNote: mockDeleteNote,
      toggleNotePin: mockToggleNotePin,
      fetchBibliography: mockFetchBibliography,
      downloadBibliography: mockDownloadBibliography,
      clearError: mockClearError,
    });

    mockProjectService.listDrafts.mockResolvedValue({
      drafts: [
        {
          id: 'draft-1',
          project_id: 'proj-1',
          version: 1,
          title: 'Draft One',
          themes: ['theme'],
          word_count: 500,
          citation_count: 2,
          is_current: true,
          created_at: '2026-03-25T00:00:00Z',
        },
      ],
      total: 1,
      skip: 0,
      limit: 50,
    });
    mockProjectService.getDraft.mockResolvedValue({
      id: 'draft-1',
      project_id: 'proj-1',
      version: 1,
      title: 'Draft One',
      content: 'Draft content',
      themes: ['theme'],
      word_count: 500,
      citation_count: 2,
      is_current: true,
      created_at: '2026-03-25T00:00:00Z',
    });
  });

  it('reloads drafts when project data changes while the drafts tab is active', async () => {
    render(<ProjectDetailPage />);

    await screen.findByText('Project One');

    fireEvent.click(screen.getByRole('button', { name: /drafts/i }));

    await waitFor(() => {
      expect(mockProjectService.listDrafts).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      useAgentChatStore.setState({ projectDataVersion: 1 });
    });

    await waitFor(() => {
      expect(mockProjectService.listDrafts).toHaveBeenCalledTimes(2);
    });
  });

  it('refreshes project data when the refresh button is clicked', async () => {
    const { user } = render(<ProjectDetailPage />);

    await screen.findByText('Project One');

    expect(mockFetchProject).toHaveBeenCalledTimes(1);
    expect(mockFetchProjectDocuments).toHaveBeenCalledTimes(1);
    expect(mockFetchProjectNotes).toHaveBeenCalledTimes(1);

    await act(async () => {
      await user.click(screen.getByRole('button', { name: /refresh/i }));
    });

    await waitFor(() => {
      expect(mockFetchProject).toHaveBeenCalledTimes(2);
      expect(mockFetchProjectDocuments).toHaveBeenCalledTimes(2);
      expect(mockFetchProjectNotes).toHaveBeenCalledTimes(2);
    });
  });
});
