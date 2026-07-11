import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ChatMessage } from '@/types/workspace';
import { MessageRole } from '@/types/workspace';

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
  default: { error: vi.fn(), success: vi.fn() },
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
    } as never);
  });

  it('keeps the optimistic turn visible (no skeleton) while the just-created thread loads mid-send', async () => {
    const { result } = renderHook(() => useChatSession());

    // First send in a new chat: the send path creates the thread, registers
    // the conversation with the optimistic user turn, and switches to it.
    act(() => {
      result.current.setConversations([
        {
          id: 'thread-new',
          title: 'New chat',
          messages: [
            { role: 'user' as const, content: 'first message', timestamp: 1 },
          ],
        } as never,
      ]);
    });
    act(() => {
      result.current.setActiveConversationId('thread-new');
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

    expect(
      result.current.displayedMessages.map((m) => m.content)
    ).toEqual(['first message']);
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
      result.current.setMessages([]);
      result.current.setActiveConversationId('thread-B');
      useChatStore.setState({
        currentThreadId: 'thread-B',
        isLoadingMessages: true,
        loadingThreadId: 'thread-B',
      } as never);
    });

    await waitFor(() =>
      expect(
        result.current.displayedMessages.map((m) => m.content)
      ).toEqual(['B one', 'B two'])
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
      result.current.setMessages([]);
      result.current.setActiveConversationId('thread-C');
      useChatStore.setState({
        currentThreadId: 'thread-C',
        isLoadingMessages: true,
        loadingThreadId: 'thread-C',
      } as never);
    });

    expect(result.current.displayedMessages).toEqual([]);
    expect(result.current.isLoadingMessages).toBe(true);
  });
});
