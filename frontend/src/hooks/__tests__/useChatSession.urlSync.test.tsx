import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const navigationMocks = vi.hoisted(() => ({
  push: vi.fn(),
  searchParams: {
    get: vi.fn((key: string) => (key === 'thread' ? 'thread-A' : null)),
  },
}));

const workspaceMocks = vi.hoisted(() => ({
  getOrCreateDefaultWorkspace: vi.fn(),
  getOrCreateDefaultConversation: vi.fn(),
  listThreads: vi.fn(),
  listConversations: vi.fn(),
  getThread: vi.fn(),
}));

const chatStoreMocks = vi.hoisted(() => {
  const state = {
    currentThreadId: null as string | null,
    messages: {},
    addMessageToStore: vi.fn(),
    loadOlderMessages: vi.fn(),
    loadingThreadId: null as string | null,
    messagePagination: {},
    setCurrentThread: vi.fn(),
  };
  const useStore = Object.assign(
    <T,>(selector: (store: typeof state) => T) => selector(state),
    {
      getState: () => state,
      setState: (partial: Partial<typeof state>) =>
        Object.assign(state, partial),
    }
  );
  return { state, useStore };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigationMocks.push, replace: vi.fn() }),
  useSearchParams: () => navigationMocks.searchParams,
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

vi.mock('@/store/chat-store', () => ({
  useChatStore: chatStoreMocks.useStore,
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: workspaceMocks,
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { useChatSession } from '@/hooks/chat/useChatSession';

describe('useChatSession URL synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigationMocks.searchParams.get.mockImplementation((key: string) =>
      key === 'thread' ? 'thread-A' : null
    );
    chatStoreMocks.state.currentThreadId = null;
    workspaceMocks.getThread.mockReset();
    workspaceMocks.getOrCreateDefaultWorkspace.mockResolvedValue({
      id: 'workspace-1',
      name: 'Workspace',
    });
    workspaceMocks.getOrCreateDefaultConversation.mockResolvedValue({
      id: 'conv-1',
      title: 'New Chat',
    });
    workspaceMocks.listThreads.mockResolvedValue({
      threads: [],
      total: 0,
      page: 1,
      limit: 50,
      has_more: false,
    });
    workspaceMocks.listConversations.mockResolvedValue({ conversations: [] });
  });

  it('does not replay the initial URL thread while a sidebar selection is navigating', async () => {
    workspaceMocks.getThread.mockReturnValue(new Promise(() => undefined));
    const { result } = renderHook(() => useChatSession());

    await waitFor(() => expect(result.current.isInitializing).toBe(false));

    act(() => {
      result.current.setConversations([
        {
          id: 'thread-A',
          title: 'A',
          messages: [{ role: 'user', content: 'A message', timestamp: 1 }],
        } as never,
        {
          id: 'thread-B',
          title: 'B',
          messages: [{ role: 'user', content: 'B message', timestamp: 2 }],
        } as never,
      ]);
      result.current.activeConversationIdRef.current = 'thread-A';
      result.current.setActiveConversationId('thread-A');
      result.current.setMessages([
        { role: 'user', content: 'A message', timestamp: 1 },
      ]);
    });

    expect(result.current.activeConversationId).toBe('thread-A');

    // handleSelectThread updates the ref and local state synchronously, while
    // router.push has not yet updated useSearchParams (which still reports A).
    act(() => {
      result.current.activeConversationIdRef.current = 'thread-B';
      result.current.setMessages([]);
      result.current.setActiveConversationId('thread-B');
    });

    expect(result.current.activeConversationId).toBe('thread-B');
  });

  it('applies a real thread query change after initialization', async () => {
    navigationMocks.searchParams.get.mockReturnValue(null);
    const { result, rerender } = renderHook(() => useChatSession());

    await waitFor(() => expect(result.current.isInitializing).toBe(false));

    act(() => {
      result.current.setConversations([
        {
          id: 'thread-A',
          title: 'A',
          messages: [{ role: 'user', content: 'A message', timestamp: 1 }],
        } as never,
        {
          id: 'thread-B',
          title: 'B',
          messages: [{ role: 'user', content: 'B message', timestamp: 2 }],
        } as never,
      ]);
      result.current.activeConversationIdRef.current = 'thread-B';
      result.current.setActiveConversationId('thread-B');
    });

    navigationMocks.searchParams.get.mockImplementation((key: string) =>
      key === 'thread' ? 'thread-A' : null
    );
    rerender();

    await waitFor(() =>
      expect(result.current.activeConversationId).toBe('thread-A')
    );
  });

  it('ignores stale URL detail when the sidebar selection changes during fetch', async () => {
    navigationMocks.searchParams.get.mockReturnValue(null);
    let resolveThread!: (thread: unknown) => void;
    workspaceMocks.getThread.mockReturnValue(
      new Promise((resolve) => {
        resolveThread = resolve;
      })
    );
    const { result, rerender } = renderHook(() => useChatSession());

    await waitFor(() => expect(result.current.isInitializing).toBe(false));

    act(() => {
      result.current.setConversations([
        {
          id: 'thread-B',
          title: 'B',
          messages: [{ role: 'user', content: 'B message', timestamp: 2 }],
        } as never,
      ]);
      result.current.activeConversationIdRef.current = 'thread-C';
      result.current.setActiveConversationId('thread-C');
    });

    // URL navigation requests uncached A, then the user selects cached B
    // before A's detail response returns.
    navigationMocks.searchParams.get.mockImplementation((key: string) =>
      key === 'thread' ? 'thread-A' : null
    );
    chatStoreMocks.state.setCurrentThread.mockClear();
    rerender();
    await waitFor(() =>
      expect(workspaceMocks.getThread).toHaveBeenCalledWith('thread-A', {
        includeMessages: false,
      })
    );

    act(() => {
      result.current.activeConversationIdRef.current = 'thread-B';
      result.current.setActiveConversationId('thread-B');
    });

    await act(async () => {
      resolveThread({
        id: 'thread-A',
        title: 'A',
        messages: [{ role: 'user', content: 'A message', timestamp: 1 }],
      });
      await Promise.resolve();
    });

    expect(result.current.activeConversationId).toBe('thread-B');
    expect(chatStoreMocks.state.setCurrentThread).not.toHaveBeenCalledWith(
      'thread-A'
    );
  });

  it('does not project legacy detail messages before the bounded store page loads', async () => {
    navigationMocks.searchParams.get.mockReturnValue(null);
    const { result, rerender } = renderHook(() => useChatSession());

    await waitFor(() => expect(result.current.isInitializing).toBe(false));

    workspaceMocks.getThread.mockResolvedValue({
      id: 'thread-A',
      conversation_id: 'conv-1',
      title: 'A',
      status: 'active',
      last_message_at: '2026-07-14T12:00:00Z',
      message_count: 1000,
      token_count: 1000,
      created_at: '2026-07-14T12:00:00Z',
      updated_at: '2026-07-14T12:00:00Z',
      messages: Array.from({ length: 1000 }, (_, index) => ({
        id: `legacy-${index}`,
        thread_id: 'thread-A',
        role: 'user',
        content: `legacy ${index}`,
        token_count: 1,
        citations: [],
        attachments: [],
        created_at: '2026-07-14T12:00:00Z',
        updated_at: '2026-07-14T12:00:00Z',
      })),
    });
    navigationMocks.searchParams.get.mockImplementation((key: string) =>
      key === 'thread' ? 'thread-A' : null
    );
    rerender();

    await waitFor(() =>
      expect(chatStoreMocks.state.setCurrentThread).toHaveBeenCalledWith(
        'thread-A'
      )
    );
    expect(workspaceMocks.getThread).toHaveBeenCalledWith('thread-A', {
      includeMessages: false,
    });
    expect(result.current.messages).toEqual([]);
  });
});
