import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@/test/test-utils';
import { useAgentChatStore } from '@/store/agentChatStore';
import ProjectDetailPage from '../../../../app/(dashboard)/projects/[id]/page';
import { useProjectStore } from '@/store/projectStore';
import { projectService } from '@/services/projectService';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1' }),
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

jest.mock('@/store/projectStore', () => ({
  useProjectStore: jest.fn(),
}));

jest.mock('@/services/projectService', () => ({
  projectService: {
    listDrafts: jest.fn(),
    getDraft: jest.fn(),
    compareDrafts: jest.fn(),
    cancelGeneration: jest.fn(),
    generateDraft: jest.fn(),
    getGenerationStatus: jest.fn(),
    downloadDraftExport: jest.fn(),
  },
}));

jest.mock('@/components/research/ProjectHeader', () => ({
  ProjectHeader: ({ project }: { project: { name: string } }) => (
    <div>{project.name}</div>
  ),
}));
jest.mock('@/components/research/DocumentList', () => ({
  DocumentList: () => <div>Documents Content</div>,
}));
jest.mock('@/components/research/DraftGenerator', () => ({
  DraftGenerator: () => <div>Draft Generator</div>,
}));
jest.mock('@/components/research/DraftViewer', () => ({
  DraftViewer: ({ draft }: { draft: { title: string } }) => (
    <div>{draft.title}</div>
  ),
}));
jest.mock('@/components/research/DraftGenerationProgress', () => ({
  DraftGenerationProgress: () => <div>Draft Progress</div>,
}));
jest.mock('@/components/research/DraftComparison', () => ({
  DraftComparison: () => <div>Draft Comparison</div>,
}));
jest.mock('@/components/research/DraftExportModal', () => ({
  DraftExportModal: () => null,
}));
jest.mock('@/components/research/ProjectChatTab', () => ({
  ProjectChatTab: () => <div>Project Chat</div>,
}));
jest.mock('@/components/research/ExtractionMatrix', () => ({
  ExtractionMatrix: () => <div>Matrix</div>,
}));
jest.mock('@/components/research/ResearchPipeline', () => ({
  ResearchPipeline: () => <div>Pipeline</div>,
}));
jest.mock('@/components/research/NoteEditor', () => ({
  NoteEditor: () => null,
}));
jest.mock('@/components/research/NoteList', () => ({
  NoteList: () => <div>Notes</div>,
}));

const mockUseProjectStore = useProjectStore as unknown as jest.Mock;
const mockProjectService = jest.mocked(projectService);

const mockFetchProject = jest.fn().mockResolvedValue(undefined);
const mockFetchProjectDocuments = jest.fn().mockResolvedValue(undefined);
const mockFetchProjectNotes = jest.fn().mockResolvedValue(undefined);
const mockFetchBibliography = jest.fn().mockResolvedValue(undefined);
const mockDownloadBibliography = jest.fn().mockResolvedValue(undefined);
const mockRemoveDocument = jest.fn().mockResolvedValue(undefined);
const mockCreateNote = jest.fn().mockResolvedValue(undefined);
const mockUpdateNote = jest.fn().mockResolvedValue(undefined);
const mockDeleteNote = jest.fn().mockResolvedValue(undefined);
const mockToggleNotePin = jest.fn().mockResolvedValue(undefined);
const mockClearError = jest.fn();

describe('ProjectDetailPage agent sync', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
    jest.clearAllMocks();

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
