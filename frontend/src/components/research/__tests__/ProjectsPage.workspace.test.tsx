import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@/test/test-utils';
import ProjectsPage from '../../../../app/(dashboard)/projects/page';

const mockPush = vi.fn();
const mockFetchProjects = vi.fn();
const mockCreateProject = vi.fn();
const mockUpdateProject = vi.fn();
const mockDeleteProject = vi.fn();
const mockClearError = vi.fn();
const mockLoadWorkspaces = vi.fn();
const mockGetOrCreateDefaultWorkspace = vi.fn();
const mockResetProjects = vi.fn();
let mockIsAuthenticated = true;
let mockProjects: Array<{ id: string; name: string }> = [];

let mockChatState: {
  currentWorkspaceId: string | null;
  workspaces: Array<{ id: string; name: string }>;
  loadWorkspaces: typeof mockLoadWorkspaces;
};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

vi.mock('@/store/projectStore', () => ({
  useProjectStore: () => ({
    projects: mockProjects,
    loading: false,
    mutating: false,
    error: null,
    total: mockProjects.length,
    fetchProjects: mockFetchProjects,
    createProject: mockCreateProject,
    updateProject: mockUpdateProject,
    deleteProject: mockDeleteProject,
    clearError: mockClearError,
    reset: mockResetProjects,
  }),
}));

vi.mock('@/store/chat-store', () => ({
  useChatStore: (selector?: (state: typeof mockChatState) => unknown) =>
    selector ? selector(mockChatState) : mockChatState,
  selectCurrentWorkspace: (state: typeof mockChatState) =>
    state.workspaces.find((w) => w.id === state.currentWorkspaceId) || null,
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getOrCreateDefaultWorkspace: (...args: unknown[]) =>
      mockGetOrCreateDefaultWorkspace(...args),
  },
}));

vi.mock('@/components/research/ProjectList', () => ({
  ProjectList: () => <div>Project List</div>,
}));

vi.mock('@/components/research/CreateProjectModal', () => ({
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

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ProjectsPage workspace behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Vitest config has `restoreMocks: true`, so `.mockResolvedValue` set
    // at module scope gets blown away between tests. Re-arm here.
    mockFetchProjects.mockResolvedValue(undefined);
    mockCreateProject.mockResolvedValue({ id: 'project-1' });
    mockUpdateProject.mockResolvedValue(undefined);
    mockDeleteProject.mockResolvedValue(undefined);
    mockLoadWorkspaces.mockResolvedValue(undefined);
    mockGetOrCreateDefaultWorkspace.mockResolvedValue({ id: 'default-ws' });
    mockIsAuthenticated = true;
    mockProjects = [];
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

  it('clears stale projects instead of rendering them when unauthenticated', async () => {
    mockIsAuthenticated = false;
    mockProjects = [{ id: 'stale-project', name: 'Stale Project' }];

    render(<ProjectsPage />);

    await waitFor(() => {
      expect(mockResetProjects).toHaveBeenCalled();
    });
    expect(mockFetchProjects).not.toHaveBeenCalled();
    expect(screen.queryByText('Project List')).not.toBeInTheDocument();
  });
});
