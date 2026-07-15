import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { v5 as uuidv5 } from 'uuid';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
import type { ChatMessage } from '@/types/workspace';

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
    listMessages: (...args: unknown[]) => listMessagesMock(...args),
  },
}));

const QUERY = 'Find recent arXiv papers on retrieval-augmented generation';

function dbMessage(
  id: string,
  role: 'user' | 'assistant',
  content: string,
  createdAt: string
): ChatMessage {
  return {
    id,
    thread_id: 'thread-A',
    role,
    content,
    created_at: createdAt,
  } as ChatMessage;
}

function makeParams() {
  const cachedLocal: ChatPageMessage[] = [
    makeChatPageMessage({
      id: 'old-user',
      role: 'user',
      content: 'Earlier question',
      timestamp: 1,
    }),
    makeChatPageMessage({
      id: 'old-assistant',
      role: 'assistant',
      content: 'Earlier answer',
      timestamp: 2,
    }),
  ];
  return {
    messages: cachedLocal,
    displayedMessages: cachedLocal,
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    activeConversationIdRef: { current: 'thread-A' as string | null },
    dbConversation: null,
    setCurrentThread: vi.fn(),
    enableRAG: false,
  };
}

describe('useChatStreaming terminal reconciliation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.getState().reset();
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({
      currentThreadId: 'thread-A',
      messages: {
        'thread-A': [
          dbMessage(
            'old-user',
            'user',
            'Earlier question',
            '2026-07-15T00:00:00Z'
          ),
          dbMessage(
            'old-assistant',
            'assistant',
            'Earlier answer',
            '2026-07-15T00:00:01Z'
          ),
        ],
      },
      messagePagination: {
        'thread-A': { hasMore: false, loadingOlder: false, loadedCount: 2 },
      },
    });

    listMessagesMock.mockResolvedValue({
      messages: [
        dbMessage(
          'new-assistant',
          'assistant',
          'Five recent papers',
          '2026-07-15T00:00:03Z'
        ),
        dbMessage('new-user', 'user', QUERY, '2026-07-15T00:00:02Z'),
        dbMessage(
          'old-assistant',
          'assistant',
          'Earlier answer',
          '2026-07-15T00:00:01Z'
        ),
        dbMessage(
          'old-user',
          'user',
          'Earlier question',
          '2026-07-15T00:00:00Z'
        ),
      ],
      has_more: false,
    });
    streamMessageMock.mockImplementation(
      (
        _request: unknown,
        callbacks: {
          onToken: (content: string) => void;
          onDone: (payload?: unknown) => void;
        }
      ) => {
        expect(useChatStore.getState().messageFreshness['thread-A']).toBe(
          'stale'
        );
        callbacks.onToken('Five recent papers');
        callbacks.onDone({
          thread_id: 'thread-A',
          assistant_message_id: 'new-assistant',
          client_message_id: 'turn-client-id',
        });
        return Promise.resolve();
      }
    );
  });

  it('refreshes the owning thread after a same-thread completion', async () => {
    const params = makeParams();
    const refreshSpy = vi.spyOn(useChatStore.getState(), 'refreshMessages');
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit(QUERY);
    });

    expect(listMessagesMock).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({ order: 'desc' })
    );
    expect(
      useChatStore
        .getState()
        .messages['thread-A']?.map((message) => message.content)
    ).toEqual([
      'Earlier question',
      'Earlier answer',
      QUERY,
      'Five recent papers',
    ]);
    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        persistedId: 'new-assistant',
        runtimeId: 'turn-client-id',
        diagnostic: expect.objectContaining({ terminalReason: 'done' }),
      })
    );
    refreshSpy.mockRestore();
  });

  it('reconciles the durable user row after a stream error', async () => {
    let userRuntimeId = '';
    streamMessageMock.mockImplementation(
      (
        request: { messages: Array<{ client_message_id?: string }> },
        callbacks: { onError: (error: string) => void }
      ) => {
        userRuntimeId = request.messages.at(-1)?.client_message_id ?? '';
        callbacks.onError('upstream failed');
        return Promise.resolve();
      }
    );
    const refreshSpy = vi.spyOn(useChatStore.getState(), 'refreshMessages');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('trigger an error');
    });

    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        runtimeId: userRuntimeId,
        diagnostic: expect.objectContaining({
          terminalReason: 'stream-error',
        }),
      })
    );
    refreshSpy.mockRestore();
  });

  it('reconciles the durable user row when the run pauses for confirmation', async () => {
    let userRuntimeId = '';
    streamMessageMock.mockImplementation(
      (
        request: { messages: Array<{ client_message_id?: string }> },
        callbacks: {
          onConfirmation: (
            threadId: string,
            confirmation: Record<string, unknown>
          ) => void;
          onDone: (payload?: unknown) => void;
        }
      ) => {
        userRuntimeId = request.messages.at(-1)?.client_message_id ?? '';
        callbacks.onConfirmation('agent-thread-a', { tool: 'create_note' });
        callbacks.onDone({});
        return Promise.resolve();
      }
    );
    const refreshSpy = vi.spyOn(useChatStore.getState(), 'refreshMessages');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('create a note');
    });

    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        runtimeId: userRuntimeId,
        diagnostic: expect.objectContaining({
          terminalReason: 'confirmation-paused',
        }),
      })
    );
    refreshSpy.mockRestore();
  });

  it('opportunistically reconciles the deterministic assistant row after stop', async () => {
    let release!: () => void;
    let callbacks!: { onToken: (content: string) => void };
    let userRuntimeId = '';
    streamMessageMock.mockImplementation(
      (
        request: { messages: Array<{ client_message_id?: string }> },
        streamCallbacks: { onToken: (content: string) => void }
      ) => {
        userRuntimeId = request.messages.at(-1)?.client_message_id ?? '';
        callbacks = streamCallbacks;
        return new Promise<void>((resolve) => {
          release = resolve;
        });
      }
    );
    const refreshSpy = vi.spyOn(useChatStore.getState(), 'refreshMessages');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    let submission!: Promise<void>;
    act(() => {
      submission = result.current.handleSubmit('stop this response');
    });
    await vi.waitFor(() => expect(streamMessageMock).toHaveBeenCalledOnce());
    await act(async () => {
      callbacks.onToken('partial answer');
      result.current.handleStop();
      release();
      await submission;
    });

    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        persistedId: undefined,
        runtimeId: uuidv5(`nous-assistant:${userRuntimeId}`, uuidv5.URL),
        diagnostic: expect.objectContaining({ terminalReason: 'stopped' }),
      })
    );
    refreshSpy.mockRestore();
  });
});
