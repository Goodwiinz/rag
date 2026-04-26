import React from 'react';
import { render, screen, waitFor } from '@/test/test-utils';
import ProjectsPage from '../../../../app/(dashboard)/projects/page';

const mockPush = jest.fn();
const mockFetchProjects = jest.fn().mockResolvedValue(undefined);
const mockCreateProject = jest.fn().mockResolvedValue({ id: 'project-1' });
const mockUpdateProject = jest.fn().mockResolvedValue(undefined);
const mockDeleteProject = jest.fn().mockResolvedValue(undefined);
const mockClearError = jest.fn();
const mockLoadWorkspaces = jest.fn().mockResolvedValue(undefined);
const mockGetOrCreateDefaultWorkspace = jest
  .fn()
  .mockResolvedValue({ id: 'default-ws' });

let mockChatState: {
  currentWorkspaceId: string | null;
  workspaces: Array<{ id: string; name: string }>;
  loadWorkspaces: typeof mockLoadWorkspaces;
};

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/store/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

jest.mock('@/store/projectStore', () => ({
  useProjectStore: () => ({
    projects: [],
    loading: false,
    error: null,
    total: 0,
    fetchProjects: mockFetchProjects,
    createProject: mockCreateProject,
    updateProject: mockUpdateProject,
    deleteProject: mockDeleteProject,
    clearError: mockClearError,
  }),
}));

jest.mock('@/store/chat-store', () => ({
  useChatStore: (selector?: (state: typeof mockChatState) => unknown) =>
    selector ? selector(mockChatState) : mockChatState,
  selectCurrentWorkspace: (state: typeof mockChatState) =>
    state.workspaces.find((w) => w.id === state.currentWorkspaceId) || null,
}));

jest.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getOrCreateDefaultWorkspace: (...args: unknown[]) =>
      mockGetOrCreateDefaultWorkspace(...args),
  },
}));

jest.mock('@/components/research/ProjectList', () => ({
  ProjectList: () => <div>Project List</div>,
}));

jest.mock('@/components/research/CreateProjectModal', () => ({
  CreateProjectModal: ({
    isOpen,
    onCreate,
  }: {
    isOpen: boolean;
    onCreate: (payload: { name: string }) => Promise<void>;
  }) =>
    isOpen ? (
      <button onClick={() => void onCreate({ name: 'Scoped Project' })}>
        Submit Project
      </button>
    ) : null,
}));

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

describe('ProjectsPage workspace behavior', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockChatState = {
      currentWorkspaceId: 'ws-selected',
      workspaces: [],
      loadWorkspaces: mockLoadWorkspaces,
    };
  });

  it('keeps project fetching scoped to the persisted workspace id after a refresh', async () => {
    render(<ProjectsPage />);

    await waitFor(() => {
      expect(mockFetchProjects).toHaveBeenCalled();
    });

    expect(mockFetchProjects).toHaveBeenCalledWith(
      expect.objectContaining({
        workspace_id: 'ws-selected',
      }),
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      })
    );
  });

  it('creates a project in the selected workspace instead of the default one', async () => {
    const { user } = render(<ProjectsPage />);

    await user.click(
      screen.getAllByRole('button', { name: /create project/i })[0]
    );
    await user.click(screen.getByRole('button', { name: /submit project/i }));

    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalledWith(
        expect.objectContaining({
          workspace_id: 'ws-selected',
          name: 'Scoped Project',
        })
      );
    });

    expect(mockGetOrCreateDefaultWorkspace).not.toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith('/projects/project-1');
  });
});
