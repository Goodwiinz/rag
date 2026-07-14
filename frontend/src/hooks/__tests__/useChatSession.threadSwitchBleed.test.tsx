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
import { mapStoreMessagesToChatMessages } from '@/components/chat/shared/cloudMessageView';

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
  // A's local transcript, as it legitimately sits in `messages` after viewing A.
  const threadAlocal = mapStoreMessagesToChatMessages(threadAStore);

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

  it('adopts thread B into local messages on switch — no thread A bleed', async () => {
    const { result } = renderHook(() => useChatSession());

    // thread-A has a populated local cache (user already viewed it) → landing on
    // A takes the cached branch and sets local `messages` to A's 5. thread-B has
    // NO local cache but IS in the store → switching to it hits the store-guard.
    act(() => {
      result.current.setConversations([
        { id: 'thread-A', title: 'A', messages: threadAlocal } as never,
        { id: 'thread-B', title: 'B', messages: [] } as never,
      ]);
    });

    // Land on A first: local messages become A's 5 (the previous transcript).
    act(() => {
      result.current.setActiveConversationId('thread-A');
    });
    await waitFor(() =>
      expect(result.current.messages.map((m) => m.content)).toEqual([
        'A one',
        'A two',
        'A three',
        'A four',
        'A five',
      ])
    );

    // Switch A -> B. Store already has B (short). Pre-fix, the store-guard
    // early-returns WITHOUT calling setMessages, so local `messages` stays A's 5
    // and the length-based display merge renders A under B (the bleed).
    act(() => {
      result.current.setActiveConversationId('thread-B');
    });

    await waitFor(() =>
      expect(result.current.messages.map((m) => m.content)).toEqual([
        'B one',
        'B two',
      ])
    );

    // Displayed (local+store merge) must also be B's 2, never A's 5.
    expect(result.current.displayedMessages.map((m) => m.content)).toEqual([
      'B one',
      'B two',
    ]);
    // Store already had B => we must NOT have re-fetched via getThread.
    expect(getThreadMock).not.toHaveBeenCalled();
  });

  it('clears thread A and waits for the single paginated store load on a cache miss', async () => {
    getThreadMock.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setConversations([
        { id: 'thread-A', title: 'A', messages: threadAlocal } as never,
        { id: 'thread-C', title: 'C', messages: [] } as never,
      ]);
    });
    act(() => {
      result.current.setActiveConversationId('thread-A');
    });
    await waitFor(() => expect(result.current.messages).toHaveLength(5));

    act(() => {
      result.current.setActiveConversationId('thread-C');
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
});
