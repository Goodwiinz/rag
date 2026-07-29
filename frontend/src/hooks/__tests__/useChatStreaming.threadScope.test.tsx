/**
 * CX5: streaming state is global (`isStreaming`/`streamingContent`/…) with no
 * record of WHICH thread owns the live turn. Send in thread A, switch to
 * thread B mid-stream: every consumer keyed only on the global flag renders
 * A's in-flight turn on B. Fix: stamp `streamingThreadId` alongside the
 * existing global flags for every live-stream owner (handleSubmit's
 * runStreamTurn AND the separate HITL confirm-resume path), so thread-scoped
 * consumers can gate on `streamingThreadId === activeThreadId` while the
 * composer keeps blocking globally (single-flight is unchanged).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
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
const streamConfirmMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: (...args: unknown[]) => streamConfirmMock(...args),
    // The hook probes for a parked HITL confirmation on thread activation;
    // nothing is parked in these scenarios.
    resumeStream: vi.fn().mockResolvedValue({ resumed: false }),
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
import { useAgentActivityStore } from '@/stores/agentActivityStore';

type StreamCallbacks = {
  onToken: (t: string) => void;
  onConfirmation: (
    threadId: string,
    confirmation: Record<string, unknown>
  ) => void;
  onDone: (p?: unknown) => void;
};

function makeParams(activeConversationId = 'thread-A') {
  useChatStore.setState({ currentThreadId: activeConversationId });
  return {
    messages: [] as ChatPageMessage[],
    // Required since CX2 (#1109) made handleSubmit build the turn from the
    // reconciled view; this suite (written pre-CX2) never provided it, so
    // every submit threw "history is not iterable".
    displayedMessages: [] as ChatPageMessage[],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId,
    setActiveConversationId: vi.fn(),
    activeConversationIdRef: {
      current: activeConversationId as string | null,
    },
    dbConversation: null,
    isAuthenticated: true,
    setCurrentThread: vi.fn(),
    addMessageToStore: vi.fn(),
    enableRAG: false,
  };
}

describe('useChatStreaming CX5 thread-scoped streaming state', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockReset();
    useChatStore.setState({ isStreaming: false, streamingThreadId: null });
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('stamps streamingThreadId for the turn thread and clears it on completion', async () => {
    let releaseStream!: () => void;
    let cb!: StreamCallbacks;
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: StreamCallbacks) =>
        new Promise<void>((resolve) => {
          cb = callbacks;
          releaseStream = resolve;
        })
    );

    const params = makeParams('thread-A');
    const { result } = renderHook(() => useChatStreaming(params), {
      wrapper,
    });

    let submitPromise!: Promise<void>;
    act(() => {
      submitPromise = result.current.handleSubmit('hi');
    });

    expect(useChatStore.getState().streamingThreadId).toBe('thread-A');

    await act(async () => {
      cb.onToken('hello');
      cb.onDone({});
      releaseStream();
      await submitPromise;
    });

    expect(useChatStore.getState().streamingThreadId).toBeNull();
  });

  it('does not leave a stale streamingThreadId after an early-exit (no content) unwind', async () => {
    // No tokens, no confirmation, no error: the "empty response" early-exit
    // branch must clear streamingThreadId same as the happy path.
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: StreamCallbacks) => {
        callbacks.onDone({});
        return Promise.resolve();
      }
    );

    const params = makeParams('thread-A');
    const { result } = renderHook(() => useChatStreaming(params), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('hi');
    });

    expect(useChatStore.getState().streamingThreadId).toBeNull();
  });

  it('stamps streamingThreadId for the HITL confirm-resume path (separate from runStreamTurn) and clears it after', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, callbacks: StreamCallbacks) => {
        callbacks.onConfirmation('agent-thread-1', {
          tool: 'ingest_arxiv_papers',
        });
        callbacks.onDone({});
        return Promise.resolve();
      }
    );

    let releaseConfirm!: () => void;
    let confirmCb!: StreamCallbacks;
    streamConfirmMock.mockImplementation(
      (_req: unknown, callbacks: StreamCallbacks) =>
        new Promise<void>((resolve) => {
          confirmCb = callbacks;
          releaseConfirm = resolve;
        })
    );

    const params = makeParams('thread-A');
    const { result } = renderHook(() => useChatStreaming(params), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    let confirmPromise!: Promise<void>;
    act(() => {
      confirmPromise = result.current.handleConfirmation(true);
    });

    expect(useChatStore.getState().streamingThreadId).toBe('thread-A');

    await act(async () => {
      confirmCb.onToken('confirmed answer');
      confirmCb.onDone({});
      releaseConfirm();
      await confirmPromise;
    });

    expect(useChatStore.getState().streamingThreadId).toBeNull();
  });
});
