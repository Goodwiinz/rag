import { describe, expect, it, vi, beforeEach } from 'vitest';
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
const streamConfirmMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: (...args: unknown[]) => streamConfirmMock(...args),
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

type StreamCallbacks = {
  onToken: (t: string) => void;
  onToolStart: (tool: string, args?: Record<string, unknown>) => void;
  onToolEnd: (tool: string, result: string, isError: boolean) => void;
  onDone: (p?: unknown) => void;
};

function makeParams() {
  return {
    messages: [] as ChatPageMessage[],
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

describe('useChatStreaming main-stream done tool_executions', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockReset();
  });

  it('commits tools from the done payload even when no live tool frames arrived', async () => {
    // Reproduces "tools only render after refresh": the wire delivered tokens
    // but NO tool_start/tool_end frames — the committed bubble must still show
    // tools, reconciled from the graph-final executions in the done payload.
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onToken('here is the answer');
        cb.onDone({
          tool_executions: [
            {
              id: 't1',
              tool_name: 'search_documents',
              tool_display_name: 'Search Documents',
              args: { query: 'photosynthesis' },
              status: 'completed',
              result: { message: 'found 3 docs' },
              duration_ms: 4321,
            },
          ],
        });
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('tell me about photosynthesis');
    });

    const calls = params.setMessages.mock.calls;
    const lastArg = calls[calls.length - 1][0] as ChatPageMessage[];
    const committed = lastArg[lastArg.length - 1];
    expect(committed).toMatchObject({
      role: 'assistant',
      content: 'here is the answer',
      toolExecutions: [
        { tool: 'search_documents', status: 'done', durationMs: 4321 },
      ],
      metadata: { toolsUsed: ['Search Documents'] },
    });
  });
});
