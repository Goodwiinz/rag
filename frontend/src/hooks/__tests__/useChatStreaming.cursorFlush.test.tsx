/**
 * Round-3 L5: the seq cursor is written through a rAF, so unmounting mid-turn
 * dropped the newest seq and the next resume replayed more than it needed.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStore } from '@/store/chat-store';

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const streamMessageMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: vi.fn(),
    resumeStream: vi.fn().mockResolvedValue({ status: 'idle' }),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn().mockResolvedValue({ messages: [], has_more: false }),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

describe('useChatStreaming seq cursor', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    useChatStore.getState().reset();
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({ currentThreadId: 'thread-A' });
  });

  it('flushes the pending cursor when the hook unmounts mid-turn (L5)', async () => {
    // rAF never fires in this test, so the cursor only lands if unmount
    // flushes it.
    vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation(
      () => 1 as unknown as number
    );
    vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => {});

    let callbacks!: { onSeq: (seq: number) => void };
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: { onSeq: (seq: number) => void }) => {
        callbacks = cb;
        return new Promise<void>(() => {});
      }
    );

    const params = {
      messages: [] as ChatPageMessage[],
      displayedMessages: [] as ChatPageMessage[],
      setMessages: vi.fn(),
      conversations: [],
      setConversations: vi.fn(),
      activeConversationId: 'thread-A',
      setActiveConversationId: vi.fn(),
      activeConversationIdRef: { current: 'thread-A' as string | null },
      dbConversation: null,
      isAuthenticated: true,
      setCurrentThread: vi.fn(),
      addMessageToStore: vi.fn(),
      enableRAG: false,
    };

    const { result, unmount } = renderHook(
      () =>
        useChatStreaming(
          params as unknown as Parameters<typeof useChatStreaming>[0]
        ),
      { wrapper }
    );

    await act(async () => {
      void result.current.handleSubmit('hello');
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    act(() => callbacks.onSeq(42));

    expect(
      useAgentActivityStore.getState().runs['thread-A']?.streamSeq
    ).not.toBe(42);

    unmount();

    expect(useAgentActivityStore.getState().runs['thread-A']?.streamSeq).toBe(
      42
    );
  });
});
