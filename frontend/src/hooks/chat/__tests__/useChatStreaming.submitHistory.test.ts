// CX2: page renders selectDisplayedMessages(local, store) but handleSubmit
// POSTs from the local array. Store-populated + local-empty (the lazy-load
// window after a thread switch) must still send full history.
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
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
const listMessagesMock = vi.fn();
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
    listMessages: (...args: unknown[]) => listMessagesMock(...args),
  },
}));

const storeBacked2: ChatPageMessage[] = [
  makeChatPageMessage({
    id: 'first-user',
    role: 'user',
    content: 'first turn',
    timestamp: 1,
  }),
  makeChatPageMessage({
    id: 'first-assistant',
    role: 'assistant',
    content: 'first reply',
    timestamp: 2,
  }),
];

function makeParams(overrides: Record<string, unknown> = {}) {
  useChatStore.setState({ currentThreadId: 'thread-A' });
  return {
    messages: [] as ChatPageMessage[],
    displayedMessages: storeBacked2,
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    activeConversationIdRef: { current: 'thread-A' as string | null },
    dbConversation: null,
    setCurrentThread: vi.fn(),
    enableRAG: false,
    ...overrides,
  };
}

describe('useChatStreaming submit history (CX2)', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    listMessagesMock.mockResolvedValue({ messages: [], has_more: false });
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: { onDone?: (p?: unknown) => void }) => {
        cb.onDone?.({});
        return Promise.resolve();
      }
    );
  });

  it('sends store-backed history when local messages are empty', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('follow-up');
    });

    const payload = streamMessageMock.mock.calls[0][0] as {
      messages: unknown[];
    };
    expect(payload.messages).toHaveLength(3); // 2 history + new turn
  });

  it('keeps React-local state limited to the optimistic overlay', async () => {
    streamMessageMock.mockImplementation(
      (
        _request: unknown,
        callbacks: {
          onToken: (content: string) => void;
          onDone: (payload?: unknown) => void;
        }
      ) => {
        callbacks.onToken('follow-up answer');
        callbacks.onDone({ assistant_message_id: 'assistant-2' });
        return Promise.resolve();
      }
    );
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('follow-up');
    });

    const arrayWrites = params.setMessages.mock.calls
      .map((call) => call[0])
      .filter((value): value is ChatPageMessage[] => Array.isArray(value));
    const finalLocalOverlay = arrayWrites.at(-1)!;
    expect(finalLocalOverlay.map((message) => message.content)).toEqual([
      'follow-up',
      'follow-up answer',
    ]);
  });
});
