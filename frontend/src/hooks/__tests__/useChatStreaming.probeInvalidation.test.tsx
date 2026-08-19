/**
 * Round-3 L2 + L7: the cold-load HITL probe must be abandoned when a new
 * submit makes it stale (its late confirmation frame armed a phantom gate),
 * and must detach immediately when the replay shows a live run instead of a
 * parked confirmation.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
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

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
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

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

type ProbeCallbacks = {
  onConfirmation: (threadId: string, c: Record<string, unknown>) => void;
  onToken?: (t: string) => void;
};

function makeParams(): Record<string, unknown> {
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

describe('useChatStreaming cold-load probe invalidation', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    resumeStreamMock.mockReset();
    useChatStore.getState().reset();
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({ currentThreadId: 'thread-A' });
  });

  it('a probe raced by a submit cannot arm a phantom gate (L2)', async () => {
    let probeCallbacks!: ProbeCallbacks;
    let probeSignal!: AbortSignal;
    resumeStreamMock.mockImplementation(
      (
        _threadId: string,
        _afterSeq: number,
        cb: ProbeCallbacks,
        signal: AbortSignal
      ) => {
        probeCallbacks = cb;
        probeSignal = signal;
        // Held open — the confirmation frame will arrive after the submit.
        return new Promise(() => {});
      }
    );
    streamMessageMock.mockImplementation(
      async (_req: unknown, cb: { onDone: (p?: unknown) => void }) => {
        cb.onDone({});
      }
    );

    const params = makeParams();
    const { result } = renderHook(
      () =>
        useChatStreaming(
          params as unknown as Parameters<typeof useChatStreaming>[0]
        ),
      { wrapper }
    );
    await waitFor(() => expect(resumeStreamMock).toHaveBeenCalled());

    await act(async () => {
      await result.current.handleSubmit('new question');
    });
    expect(probeSignal.aborted).toBe(true);

    // The stale confirmation frame races in anyway.
    act(() => {
      probeCallbacks.onConfirmation('agent-thread-1', {
        tool: 'ingest_arxiv_papers',
      });
    });

    expect(result.current.pendingConfirmation).toBeNull();
  });

  it('a probe that hits a live run detaches instead of consuming it (L7)', async () => {
    let probeSignal!: AbortSignal;
    resumeStreamMock.mockImplementation(
      (
        _threadId: string,
        _afterSeq: number,
        cb: ProbeCallbacks,
        signal: AbortSignal
      ) => {
        probeSignal = signal;
        // The replay opens with a token — this is a live run, not a parked
        // confirmation.
        cb.onToken?.('live token');
        return new Promise(() => {});
      }
    );

    const params = makeParams();
    renderHook(
      () =>
        useChatStreaming(
          params as unknown as Parameters<typeof useChatStreaming>[0]
        ),
      { wrapper }
    );

    await waitFor(() => expect(resumeStreamMock).toHaveBeenCalled());
    expect(probeSignal.aborted).toBe(true);
  });
});
