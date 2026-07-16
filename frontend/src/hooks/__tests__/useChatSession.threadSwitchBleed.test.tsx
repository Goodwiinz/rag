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

const getThreadMock = vi.fn();
vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getThread: (...args: unknown[]) => getThreadMock(...args),
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

describe('useChatSession thread-switch transcript bleed (I1)', () => {
  const threadAStore = [
    storeMsg('thread-A', 'a1', 'A one'),
    storeMsg('thread-A', 'a2', 'A two', MessageRole.ASSISTANT),
    storeMsg('thread-A', 'a3', 'A three'),
    storeMsg('thread-A', 'a4', 'A four', MessageRole.ASSISTANT),
    storeMsg('thread-A', 'a5', 'A five'),
  ];
  beforeEach(() => {
    getThreadMock.mockReset();
    // Store is the per-thread source of truth. Seed only B here; B is the
    // thread the store already holds but that the user is switching INTO.
    useChatStore.setState({
      messages: {
        'thread-A': threadAStore,
        'thread-B': [
          storeMsg('thread-B', 'b1', 'B one'),
          storeMsg('thread-B', 'b2', 'B two', MessageRole.ASSISTANT),
        ],
      },
      currentThreadId: null,
      isLoadingMessages: false,
      loadingThreadId: null,
    } as never);
  });

  it('keeps canonical rows out of local overlay state on thread switches', async () => {
    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-A', title: 'A', messages: [] } as never,
        { id: 'thread-B', title: 'B', messages: [] } as never,
      ]);
    });

    // Canonical store rows render directly; React-local state remains an
    // optimistic/local-only overlay instead of becoming a second transcript.
    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-A' });
    });
    await waitFor(() =>
      expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
        'A one',
        'A two',
        'A three',
        'A four',
        'A five',
      ])
    );
    expect(result.current.messages).toEqual([]);

    // Switch A -> B. Store already has B (short). Pre-fix, the store-guard
    // early-returns WITHOUT calling setMessages, so local `messages` stays A's 5
    // and the length-based display merge renders A under B (the bleed).
    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-B' });
    });

    await waitFor(() => expect(result.current.messages).toEqual([]));

    // Displayed (local+store merge) must also be B's 2, never A's 5.
    expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
      'B one',
      'B two',
    ]);
    // Store already had B => we must NOT have re-fetched via getThread.
    expect(getThreadMock).not.toHaveBeenCalled();
  });

  // Task 5.5 mutation-verified: the `isLoadingMessages` value this test reads
  // gates on `isThreadSwitchPending` (`src/components/chat/shared/
  // cloudMessageView.ts`) — true only while the active thread's initial page
  // is loading and nothing is renderable yet. Forcing that guard to `false`
  // fails this test's `expect(result.current.isLoadingMessages).toBe(true)`
  // assertion (see docs/testing/chat-mutation-checks.md item 6).
  it('clears thread A and waits for the single paginated store load on a cache miss', async () => {
    getThreadMock.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-A', title: 'A', messages: [] } as never,
        { id: 'thread-C', title: 'C', messages: [] } as never,
      ]);
    });
    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-A' });
    });
    await waitFor(() =>
      expect(result.current.displayedMessages).toHaveLength(5)
    );
    expect(result.current.messages).toEqual([]);

    act(() => {
      useChatStore.setState({
        currentThreadId: 'thread-C',
        isLoadingMessages: true,
        loadingThreadId: 'thread-C',
      } as never);
    });

    // The store page is in flight — A's transcript must already be gone, and
    // the hook must not start a parallel full-detail getThread request.
    expect(getThreadMock).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
    expect(result.current.displayedMessages).toEqual([]);
    expect(result.current.isLoadingMessages).toBe(true);

    act(() => {
      useChatStore.setState({
        messages: {
          ...useChatStore.getState().messages,
          'thread-C': [storeMsg('thread-C', 'c1', 'C one')],
        },
        isLoadingMessages: false,
        loadingThreadId: null,
      } as never);
    });

    await waitFor(() =>
      expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
        'C one',
      ])
    );
  });

  it('rejects a stale cache-miss load when the user rapidly switches away and back before it resolves', async () => {
    // A -> C (cache miss, hangs forever) -> B (cached), all in rapid
    // succession — the transcript must land on B, and C's eventual
    // resolution must never overwrite what is currently displayed.
    getThreadMock.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-A', title: 'A', messages: [] } as never,
        { id: 'thread-B', title: 'B', messages: [] } as never,
        { id: 'thread-C', title: 'C', messages: [] } as never,
      ]);
    });

    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-A' });
    });
    await waitFor(() =>
      expect(result.current.displayedMessages).toHaveLength(5)
    );

    // Rapid-fire: switch into the uncached thread C, then immediately away
    // to the already-cached thread B, without awaiting C's (never
    // resolving) fetch in between.
    act(() => {
      useChatStore.setState({
        currentThreadId: 'thread-C',
        isLoadingMessages: true,
        loadingThreadId: 'thread-C',
      } as never);
    });
    act(() => {
      useChatStore.setState({ currentThreadId: 'thread-B' });
    });

    await waitFor(() =>
      expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
        'B one',
        'B two',
      ])
    );
    // B was already cached, so no parallel getThread request was needed for
    // either the abandoned C switch or the landed B switch.
    expect(getThreadMock).not.toHaveBeenCalled();

    // If C's long-hanging fetch were to resolve now, it targets a thread
    // that is no longer selected — nothing observes it, so the display
    // must still be B's.
    expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
      'B one',
      'B two',
    ]);
  });
});
