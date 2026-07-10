import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

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

const createMessageMock = vi.fn().mockResolvedValue({ id: 'db-msg-1' });
vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: (...args: unknown[]) => createMessageMock(...args),
    listMessages: vi.fn(),
  },
}));

type StreamCallbacks = {
  onToken: (t: string) => void;
  onDone: (p?: unknown) => void;
};

function makeParams() {
  return {
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
}

describe('useChatStreaming server-canonical mode', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    createMessageMock.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('reconciles the bubble id from the done payload and does not self-persist', async () => {
    // Flag is a module-load-time const, so stub the env then import fresh.
    vi.stubEnv('NEXT_PUBLIC_SERVER_CANONICAL_CHAT', 'true');
    vi.resetModules();
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onToken('canonical answer');
        cb.onDone({
          thread_id: 'thread-A',
          assistant_message_id: 'srv-assistant-1',
          client_message_id: 'cmid-1',
        });
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('hello canonical');
    });

    // Committed assistant message carries the SERVER id (reconciliation), not
    // a client-generated one.
    const calls = params.setMessages.mock.calls;
    const lastArg = calls[calls.length - 1][0] as ChatPageMessage[];
    const committed = lastArg[lastArg.length - 1];
    expect(committed.role).toBe('assistant');
    expect(committed.id).toBe('srv-assistant-1');

    // Canonical mode: the client must NOT double-write rows — the backend is
    // the sole writer.
    expect(createMessageMock).not.toHaveBeenCalled();
  });
});
