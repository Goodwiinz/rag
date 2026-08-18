/**
 * onPlan must populate the store's streamingPlan (the live transcript row
 * reads it via AuiStreamingBody's StreamingPlanSection), and every terminal
 * path must clear it back to [] so a later turn doesn't inherit a stale plan.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStore } from '@/store/chat-store';

function wrapper({ children }: { children: ReactNode }): ReactElement {
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
    resumeStream: vi.fn().mockResolvedValue({ status: 'idle' }),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

import {
  useChatStreaming,
  type UseChatStreamingParams,
} from '@/hooks/chat/useChatStreaming';

type StreamCallbacks = {
  onToken: (t: string) => void;
  onPlan: (steps: Array<Record<string, unknown>>, reasoning: string) => void;
  onConfirmation: (
    threadId: string,
    confirmation: Record<string, unknown>
  ) => void;
  onDone: (p?: unknown) => void;
};

function makeParams(): UseChatStreamingParams {
  useChatStore.setState({ currentThreadId: 'thread-A' });
  return {
    messages: [] as ChatPageMessage[],
    displayedMessages: [] as ChatPageMessage[],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    dbConversation: null,
    enableRAG: false,
  };
}

describe('useChatStreaming streamingPlan', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockReset();
  });

  it('populates streamingPlan from onPlan while the main stream is live, then clears it on commit', async () => {
    const planDuringStream: unknown[][] = [];
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onPlan(
          [{ step: 1, description: 'Search arXiv', tool: 'search_arxiv' }],
          'Search arXiv, then summarize the top result.'
        );
        planDuringStream.push([...useChatStore.getState().streamingPlan]);
        cb.onToken('the answer');
        cb.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('search arxiv for transformers');
    });

    expect(planDuringStream[0]).toMatchObject([
      { description: 'Search arXiv', tool: 'search_arxiv' },
    ]);
    // Stream ended (committed) — the live copy must not leak into the next turn.
    expect(useChatStore.getState().streamingPlan).toEqual([]);
    // The rationale rides the committed message alongside the plan.
    const committedWithReasoning = (params.setMessages as ReturnType<
      typeof vi.fn
    >).mock.calls
      .map((c) => c[0])
      .filter((arg): arg is ChatPageMessage[] => Array.isArray(arg))
      .flatMap((arr) => arr)
      .find((m) => m.role === 'assistant' && !m.isStreaming);
    expect(committedWithReasoning?.planReasoning).toBe(
      'Search arXiv, then summarize the top result.'
    );
  });

  it('seeds streamingPlan from the carried pre-interrupt plan on a confirm resume, then clears it', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onPlan(
          [{ step: 1, description: 'Ingest the papers', tool: 'ingest_arxiv_papers' }],
          ''
        );
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );
    let planAtConfirmStart: unknown[] = [];
    streamConfirmMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        planAtConfirmStart = [...useChatStore.getState().streamingPlan];
        cb.onToken('confirmed answer');
        cb.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    expect(result.current.pendingConfirmation?.plan).toMatchObject([
      { description: 'Ingest the papers' },
    ]);

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    expect(planAtConfirmStart).toMatchObject([
      { description: 'Ingest the papers' },
    ]);
    expect(useChatStore.getState().streamingPlan).toEqual([]);
  });
});
