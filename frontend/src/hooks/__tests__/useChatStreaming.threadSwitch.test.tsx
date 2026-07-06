import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

// The hook calls useQueryClient — provide one for renderHook.
function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

// ---- Mocks ----
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const streamMessageMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: vi.fn(),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';

function makeParams(overrides: Partial<Parameters<typeof useChatStreaming>[0]> = {}) {
  const activeConversationIdRef = { current: 'thread-A' as string | null };
  return {
    messages: [
      { role: 'user', content: 'earlier question', timestamp: 1 },
    ] as ChatPageMessage[],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    activeConversationIdRef,
    dbConversation: null, // no thread creation path; thread-A already exists
    isAuthenticated: true,
    setCurrentThread: vi.fn(),
    addMessageToStore: vi.fn(),
    enableRAG: false,
    ...overrides,
  };
}

describe('useChatStreaming thread-switch guard', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
  });

  it('skips the final setMessages when the user switched threads mid-stream', async () => {
    // streamMessage resolves only when the test says so, after emitting tokens.
    let finishStream!: () => void;
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: { onToken: (t: string) => void; onDone: (p?: unknown) => void }) =>
        new Promise<void>((resolve) => {
          callbacks.onToken('hello from thread A');
          callbacks.onDone({});
          finishStream = resolve;
        })
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    let submitPromise!: Promise<void>;
    act(() => {
      submitPromise = result.current.handleSubmit('question for thread A');
    });

    // Simulate the sidebar switching to thread B while the stream is in flight
    // (page.tsx onSelect mutates the ref synchronously).
    params.activeConversationIdRef.current = 'thread-B';
    params.setMessages.mockClear(); // ignore the optimistic user-bubble write

    await act(async () => {
      finishStream();
      await submitPromise;
    });

    // The guard must prevent thread A's completion from writing into the
    // currently-displayed (thread B) message state.
    expect(params.setMessages).not.toHaveBeenCalled();
  });

  it('still commits the final message when the thread did NOT change', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: { onToken: (t: string) => void; onDone: (p?: unknown) => void }) => {
        callbacks.onToken('answer');
        callbacks.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('question');
    });

    // Last setMessages call must contain the assistant answer.
    const calls = params.setMessages.mock.calls;
    const lastArg = calls[calls.length - 1][0] as ChatPageMessage[];
    expect(lastArg[lastArg.length - 1]).toMatchObject({
      role: 'assistant',
      content: 'answer',
    });
  });
});
