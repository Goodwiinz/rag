import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';
import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';
import ProjectsPage from '../../../../app/(dashboard)/projects/page';

const mockPush = vi.fn();
const mockFetchProjects = vi.fn();
const mockCreateProject = vi.fn();
const mockUpdateProject = vi.fn();
const mockDeleteProject = vi.fn();
const mockClearError = vi.fn();
const mockLoadWorkspaces = vi.fn();

let mockChatState: {
  currentWorkspaceId: string | null;
  workspaces: Array<{ id: string; name: string }>;
  loadWorkspaces: typeof mockLoadWorkspaces;
};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

vi.mock('@/store/projectStore', () => ({
  useProjectStore: () => ({
    projects: [],
    loading: false,
    mutating: false,
    error: null,
    total: 0,
    fetchProjects: mockFetchProjects,
    createProject: mockCreateProject,
    updateProject: mockUpdateProject,
    deleteProject: mockDeleteProject,
    clearError: mockClearError,
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
    getOrCreateDefaultWorkspace: vi
      .fn()
      .mockResolvedValue({ id: 'default-ws' }),
  },
}));

vi.mock('@/components/research/ProjectList', () => ({
  ProjectList: () => <div>Project List</div>,
}));

vi.mock('@/components/research/CreateProjectModal', () => ({
  CreateProjectModal: () => null,
}));

vi.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ProjectsPage search debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockFetchProjects.mockResolvedValue(undefined);
    mockLoadWorkspaces.mockResolvedValue(undefined);
    mockChatState = {
      currentWorkspaceId: 'ws-1',
      workspaces: [{ id: 'ws-1', name: 'Test Workspace' }],
      loadWorkspaces: mockLoadWorkspaces,
    };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fire a fetch per keystroke — waits for debounce window', () => {
    render(<ProjectsPage />);

    // Let mount effects flush (the initial fetch fires here)
    act(() => {
      vi.advanceTimersByTime(350);
    });

    // Record how many calls happened before typing
    mockFetchProjects.mockClear();

    const input = screen.getByPlaceholderText('Search projects...');

    // Simulate typing "machine" one character at a time using fireEvent.change
    // Each change fires synchronously, so no fake-timer conflicts
    const chars = 'machine';
    for (let i = 1; i <= chars.length; i++) {
      fireEvent.change(input, { target: { value: chars.slice(0, i) } });
    }

    // Immediately after typing — debounce timer has NOT elapsed yet
    // So NO new fetches should have been triggered
    expect(mockFetchProjects).not.toHaveBeenCalled();

    // Now advance past the 300ms debounce window
    act(() => {
      vi.advanceTimersByTime(350);
    });

    // Exactly 1 debounced fetch should fire (not 7)
    expect(mockFetchProjects).toHaveBeenCalledTimes(1);

    // That single fetch should carry the complete search term
    expect(mockFetchProjects).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'machine' }),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('sends the final search term after the debounce delay', () => {
    render(<ProjectsPage />);

    // Let mount effects flush
    act(() => {
      vi.advanceTimersByTime(350);
    });

    mockFetchProjects.mockClear();

    const input = screen.getByPlaceholderText('Search projects...');
    fireEvent.change(input, { target: { value: 'machine' } });

    // Before debounce — no fetch yet
    expect(mockFetchProjects).not.toHaveBeenCalled();

    // Advance past debounce
    act(() => {
      vi.advanceTimersByTime(350);
    });

    // Verify the fetch contains search: 'machine'
    expect(mockFetchProjects).toHaveBeenCalledTimes(1);
    expect(mockFetchProjects).toHaveBeenCalledWith(
      expect.objectContaining({ search: 'machine' }),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });
});
