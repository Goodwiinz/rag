import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const getDefaultWorkspaceMock = vi.hoisted(() => vi.fn());

vi.mock('@/services/workspaceService', () => ({
  clearWorkspaceServiceCache: vi.fn(),
  workspaceService: {
    getOrCreateDefaultWorkspace: getDefaultWorkspaceMock,
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { useChatPersistence } from '@/hooks/useChatPersistence';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';

describe('useChatPersistence initialization', () => {
  const originalActions = {
    initializeDefaultWorkspace:
      useChatStore.getState().initializeDefaultWorkspace,
    loadConversations: useChatStore.getState().loadConversations,
    loadThreads: useChatStore.getState().loadThreads,
  };

  beforeEach(() => {
    getDefaultWorkspaceMock.mockReset();
    useChatStore.setState(originalActions);
    useChatStore.getState().reset();
    useAuthStore.setState({ isAuthenticated: true });
  });

  afterEach(() => {
    useAuthStore.setState({ isAuthenticated: false });
    useChatStore.setState(originalActions);
    useChatStore.getState().reset();
  });

  it('rejects store failures and retries one shared bootstrap up to the limit', async () => {
    const bootstrapError = new Error('workspace offline');
    getDefaultWorkspaceMock.mockRejectedValueOnce(bootstrapError);

    await expect(originalActions.initializeDefaultWorkspace()).rejects.toBe(
      bootstrapError
    );
    expect(useChatStore.getState().error).toBe(
      'Failed to initialize workspace'
    );

    useChatStore.getState().reset();
    const initializeDefaultWorkspace = vi
      .fn()
      .mockRejectedValueOnce(bootstrapError)
      .mockRejectedValueOnce(bootstrapError)
      .mockImplementation(async () => {
        useChatStore.setState({
          currentWorkspaceId: 'workspace-1',
          workspaces: [{ id: 'workspace-1', name: 'Research' }] as never,
        });
      });
    let conversationsAttempt = 0;
    const loadConversations = vi.fn(async () => {
      conversationsAttempt += 1;
      if (conversationsAttempt === 1) {
        useChatStore.setState({ error: 'Failed to load conversations' });
        return;
      }
      useChatStore.setState({
        error: null,
        conversations: {
          'workspace-1': [
            {
              id: 'conversation-1',
              workspace_id: 'workspace-1',
              title: 'Chat',
            },
          ] as never,
        },
      });
    });
    let threadsAvailable = false;
    const loadThreads = vi.fn(async () => {
      if (!threadsAvailable) {
        useChatStore.setState({ error: 'Failed to load threads' });
        return;
      }
      useChatStore.setState({
        error: null,
        threads: { 'conversation-1': [] },
      });
    });
    useChatStore.setState({
      initializeDefaultWorkspace,
      loadConversations,
      loadThreads,
    });

    const first = renderHook(() => useChatPersistence());
    renderHook(() => useChatPersistence());

    await waitFor(() => expect(loadConversations).toHaveBeenCalledTimes(1));
    expect(useChatStore.getState().currentConversationId).toBeNull();

    await act(async () => {
      await first.result.current.initialize();
    });
    await waitFor(() => expect(loadThreads).toHaveBeenCalledTimes(2));
    expect(useChatStore.getState().error).toBe('Failed to load threads');

    threadsAvailable = true;
    await act(async () => {
      await first.result.current.initialize();
    });
    await waitFor(() => expect(useChatStore.getState().error).toBeNull());
    expect(useChatStore.getState().currentConversationId).toBe(
      'conversation-1'
    );
    expect(initializeDefaultWorkspace).toHaveBeenCalledTimes(5);
    expect(loadConversations).toHaveBeenCalledTimes(3);
    // setCurrentConversation starts the store load, then bootstrap awaits its
    // own load so it can verify completion before marking initialization done.
    expect(loadThreads).toHaveBeenCalledTimes(3);
  });
});
