/**
 * Round-3 M5: a turn that failed mid-stream leaves a local-only error bubble.
 * When the turn recovers, its own answer used to be appended BELOW that bubble
 * and both stayed visible until a reload.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
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
const resumeStreamMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: vi.fn(),
    resumeStream: (...args: unknown[]) => resumeStreamMock(...args),
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

describe('useChatStreaming recovery cleanup', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    resumeStreamMock.mockReset();
    resumeStreamMock.mockResolvedValue({ status: 'idle' });
    useChatStore.getState().reset();
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({ currentThreadId: 'thread-A' });
  });

  it('drops a stale local-only error bubble when the resumed turn commits (M5)', async () => {
    // The turn already failed once: the run is still 'running' server-side and
    // the transcript carries the transient error bubble the failure rendered.
    useAgentActivityStore.getState().startRun('thread-A', 'Agent', 'task');
    resumeStreamMock.mockImplementation(
      async (
        _threadId: string,
        _afterSeq: number,
        cb: { onToken: (t: string) => void; onDone: (p?: unknown) => void }
      ) => {
        cb.onToken('recovered answer');
        cb.onDone({});
        return { status: 'resumed' };
      }
    );

    const priorMessages: ChatPageMessage[] = [
      makeChatPageMessage({
        id: 'u1',
        role: 'user',
        content: 'earlier question',
        timestamp: 1,
      }),
      {
        runtimeId: 'err-1',
        source: 'local-only',
        role: 'assistant',
        content: '',
        timestamp: 2,
        error: {
          message: 'Something went wrong sending your message.',
          category: 'exception',
        },
      } as ChatPageMessage,
    ];

    const setMessages = vi.fn();
    const params = {
      messages: priorMessages,
      displayedMessages: priorMessages,
      setMessages,
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

    await act(async () => {
      renderHook(
        () =>
          useChatStreaming(
            params as unknown as Parameters<typeof useChatStreaming>[0]
          ),
        { wrapper }
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const committed = setMessages.mock.calls
      .map((call) => call[0])
      .filter((arg): arg is ChatPageMessage[] => Array.isArray(arg))
      .at(-1);

    expect(committed).toBeDefined();
    expect(
      committed!.some(
        (message) => message.source === 'local-only' && message.error
      )
    ).toBe(false);
    expect(committed!.at(-1)).toMatchObject({
      role: 'assistant',
      content: 'recovered answer',
    });
  });
});
