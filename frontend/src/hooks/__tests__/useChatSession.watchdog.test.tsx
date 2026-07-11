import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

const workspaceMocks = vi.hoisted(() => ({
  getOrCreateDefaultWorkspace: vi.fn(),
  getOrCreateDefaultConversation: vi.fn(),
  listThreads: vi.fn(),
  listConversations: vi.fn(),
}));

const chatStoreMocks = vi.hoisted(() => {
  const state = {
    currentThreadId: null as string | null,
    messages: {} as Record<string, []>,
    addMessageToStore: vi.fn(),
    loadOlderMessages: vi.fn(),
    messagePagination: {},
    isLoadingMessages: false,
    setCurrentThread: vi.fn(),
  };
  state.setCurrentThread.mockImplementation((threadId: string | null) => {
    state.currentThreadId = threadId;
  });
  const useStore = Object.assign(
    <T,>(selector: (store: typeof state) => T) => selector(state),
    { getState: () => state }
  );
  return { state, useStore };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: workspaceMocks,
}));

vi.mock('@/store/chat-store', () => ({
  useChatStore: chatStoreMocks.useStore,
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

import { useChatSession } from '@/hooks/chat/useChatSession';

describe('useChatSession watchdog', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    chatStoreMocks.state.currentThreadId = null;
    workspaceMocks.getOrCreateDefaultConversation.mockResolvedValue({
      id: 'conv-1',
      title: 'New Chat',
    });
    workspaceMocks.listThreads.mockResolvedValue({ threads: [] });
    workspaceMocks.listConversations.mockResolvedValue({ conversations: [] });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('clears the timeout error when initialization eventually succeeds', async () => {
    let resolveWorkspace!: (workspace: { id: string; name: string }) => void;
    workspaceMocks.getOrCreateDefaultWorkspace.mockReturnValue(
      new Promise((resolve) => {
        resolveWorkspace = resolve;
      })
    );

    const { result } = renderHook(() => useChatSession());

    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(result.current.initError).toContain('taking longer than expected');

    await act(async () => {
      resolveWorkspace({ id: 'workspace-1', name: 'Workspace' });
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.isInitializing).toBe(false);
    expect(result.current.initError).toBeNull();
  });
});
