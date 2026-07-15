import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ChatMessage } from '@/types/workspace';
import { MessageRole } from '@/types/workspace';

const toastMocks = vi.hoisted(() => ({ error: vi.fn() }));

// ---- Mocks ----
// Unauthenticated => useChatSession's init effect settles immediately, leaves
// conversations empty and skips all DB fetches. We then drive state purely via
// the returned setters, so no init/URL/sync effect races our seeded state.
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: false }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  // No ?thread= => the URL-switch effect is inert.
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getThread: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { error: toastMocks.error, success: vi.fn() },
}));

import { useChatSession } from '@/hooks/chat/useChatSession';
import { useChatStore } from '@/store/chat-store';

function storeMsg(
  threadId: string,
  id: string,
  content: string,
  role: MessageRole = MessageRole.USER
): ChatMessage {
  return {
    id,
    thread_id: threadId,
    content,
    role,
    token_count: 0,
    citations: [],
    attachments: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// Pins the scoping of the thread-loading UI state (#1121 follow-up): the
// store's message-page fetch must only blank/skeleton the transcript when it
// is the ACTIVE thread's first page and there is nothing renderable yet —
// never during a send (local optimistic turn present) and never over a
// cached transcript.
describe('useChatSession thread-load scoping', () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: {},
      currentThreadId: null,
      isLoadingMessages: false,
      loadingThreadId: null,
      error: null,
    } as never);
    toastMocks.error.mockReset();
  });

  it('keeps the optimistic turn visible (no skeleton) while the just-created thread loads mid-send', async () => {
    const { result } = renderHook(() => useChatSession());

    // First send in a new chat: the optimistic turn is the local overlay while
    // conversation metadata deliberately carries no transcript copy.
    act(() => {
      result.current.setConversations([
        {
          id: 'thread-new',
          title: 'New chat',
          messages: [],
        } as never,
      ]);
      result.current.setMessages([
        {
          runtimeId: 'runtime-first',
          source: 'optimistic',
          role: 'user',
          content: 'first message',
          timestamp: 1,
        },
      ]);
    });
    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-new' });
    });
    await waitFor(() =>
      expect(result.current.messages.map((m) => m.content)).toEqual([
        'first message',
      ])
    );

    // setCurrentThread(newId) side effect: the store fetches the (empty) new
    // thread's page — mid-send this must not hide the transcript.
    act(() => {
      useChatStore.setState({
        currentThreadId: 'thread-new',
        isLoadingMessages: true,
        loadingThreadId: 'thread-new',
      } as never);
    });

    expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
      'first message',
    ]);
    expect(result.current.isLoadingMessages).toBe(false);
  });

  it('shows the cached transcript instantly (no skeleton) while a background refresh is in flight', async () => {
    useChatStore.setState({
      messages: {
        'thread-B': [
          storeMsg('thread-B', 'b1', 'B one'),
          storeMsg('thread-B', 'b2', 'B two', MessageRole.ASSISTANT),
        ],
      },
    } as never);

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-B', title: 'B', messages: [] } as never,
      ]);
    });
    // Switch into B exactly like the page does: clear local, point store at
    // B with its (always-refetching) initial page load in flight.
    act(() => {
      useChatStore.setState({
        currentThreadId: 'thread-B',
        isLoadingMessages: true,
        loadingThreadId: 'thread-B',
      } as never);
    });

    await waitFor(() =>
      expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
        'B one',
        'B two',
      ])
    );
    expect(result.current.isLoadingMessages).toBe(false);
  });

  it('reports loading (skeleton) while an uncached thread switch is in flight', () => {
    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-C', title: 'C', messages: [] } as never,
      ]);
    });
    act(() => {
      useChatStore.setState({
        currentThreadId: 'thread-C',
        isLoadingMessages: true,
        loadingThreadId: 'thread-C',
      } as never);
    });

    expect(result.current.displayedMessages).toEqual([]);
    expect(result.current.isLoadingMessages).toBe(true);
  });

  it('surfaces a failed active-thread page load instead of presenting an empty conversation', async () => {
    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        {
          id: 'thread-C',
          title: 'C',
          messages: [],
          messageCount: 2,
        } as never,
      ]);
      useChatStore.setState({
        currentThreadId: 'thread-C',
        isLoadingMessages: true,
        loadingThreadId: 'thread-C',
        error: null,
      } as never);
    });

    act(() => {
      useChatStore.setState({
        isLoadingMessages: false,
        loadingThreadId: null,
        error: 'Failed to load messages',
      } as never);
    });

    await waitFor(() =>
      expect(toastMocks.error).toHaveBeenCalledWith(
        'Could not load this conversation. Please try again.'
      )
    );
  });
});
