import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStore } from '@/store/chat-store';

function wrapper({ children }: { children: ReactNode }) {
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
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

type StreamCallbacks = {
  onToken: (t: string) => void;
  onDone: (p?: unknown) => void;
};

function makeParams(setMessages: (m: ChatPageMessage[]) => void) {
  useChatStore.setState({ currentThreadId: 'thread-A' });
  return {
    messages: [] as ChatPageMessage[],
    displayedMessages: [] as ChatPageMessage[],
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
}

describe('useChatStreaming in-flight placeholder', () => {
  beforeEach(() => streamMessageMock.mockReset());
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('adds a streaming placeholder at start and replaces it on done', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    // Resolve setMessages to concrete snapshots (the hook uses both array and
    // updater forms).
    let current: ChatPageMessage[] = [];
    const snapshots: ChatPageMessage[][] = [];
    const setMessages = vi.fn(
      (
        m: ChatPageMessage[] | ((p: ChatPageMessage[]) => ChatPageMessage[])
      ) => {
        current = typeof m === 'function' ? m(current) : m;
        snapshots.push(current);
      }
    );

    let sawPlaceholderDuringStream = false;
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        if (!cb) return Promise.resolve();
        // Placeholder is appended synchronously before start() is awaited.
        sawPlaceholderDuringStream = current.some((m) => m.isStreaming);
        cb.onToken('the answer');
        cb.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams(setMessages);
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('a question');
    });

    // A streaming placeholder was present in the transcript while the stream
    // was in flight...
    expect(sawPlaceholderDuringStream).toBe(true);

    // ...and the committed turn replaced it: the final list ends with a
    // non-streaming assistant message carrying the streamed content, and no
    // placeholder survives anywhere.
    const finalList = snapshots[snapshots.length - 1];
    const committed = finalList[finalList.length - 1];
    expect(committed).toMatchObject({
      role: 'assistant',
      content: 'the answer',
    });
    expect(committed.isStreaming).toBeFalsy();
    expect(finalList.some((m) => m.isStreaming)).toBe(false);
  });
});
