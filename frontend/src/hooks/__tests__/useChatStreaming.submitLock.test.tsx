/**
 * submitLockRef single-flight guard (recon `chatfe.guards` — "SUBMIT
 * single-flight"): useChatStreaming.ts stamps a synchronous ref at the top
 * of handleSubmit so a second call arriving before the first has released
 * the lock (fast double Enter / composer re-submit in the same tick) is a
 * no-op, mirroring the CX1 confirmLockRef belt tested in
 * useChatStreaming.confirmToolSteps.test.tsx. No existing test exercised
 * this path — added per the Task 5.5 mutation-verification sweep.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStore } from '@/store/chat-store';
import type { UseChatStreamingParams } from '@/hooks/chat/useChatStreaming';

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
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...args: unknown[]) => streamMessageMock(...args),
    streamConfirm: vi.fn(),
    // The hook probes for a parked HITL confirmation on thread activation;
    // nothing is parked in these scenarios.
    resumeStream: vi.fn().mockResolvedValue({ status: 'idle' }),
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
import { workspaceService } from '@/services/workspaceService';

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

describe('useChatStreaming submit single-flight (submitLockRef)', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    useChatStore.getState().reset();
  });

  it('a synchronous second handleSubmit call while the first is still in flight only fires streamMessage once', async () => {
    let releaseStream!: () => void;
    streamMessageMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          releaseStream = resolve;
        })
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), {
      wrapper,
    });

    // Two handleSubmit calls in the same tick, before the first
    // streamMessage call has resolved — mirrors a fast double Enter/click.
    // The second call must be blocked client-side (submitLockRef).
    let p1!: Promise<void>;
    let p2!: Promise<void>;
    act(() => {
      p1 = result.current.handleSubmit('first message');
      p2 = result.current.handleSubmit('second message');
    });

    expect(streamMessageMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      releaseStream();
      await Promise.all([p1, p2]);
    });

    // Still exactly one call after both promises settle.
    expect(streamMessageMock).toHaveBeenCalledTimes(1);
    // The lock released so a later, legitimate submit isn't stuck.
    expect(result.current.isLoading).toBe(false);

    // Prove the lock actually releases: a genuine subsequent submit reaches
    // streamMessage again, rather than relying on the isLoading flag alone.
    streamMessageMock.mockResolvedValueOnce(undefined);
    await act(async () => {
      await result.current.handleSubmit('later message');
    });
    expect(streamMessageMock).toHaveBeenCalledTimes(2);
  });

  it('does not start streaming when Stop lands during first-thread creation', async () => {
    let finishThreadCreation!: (thread: unknown) => void;
    vi.mocked(workspaceService.createThread).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishThreadCreation = resolve;
        }) as never
    );
    const originalMessages: ChatPageMessage[] = [];
    const params = {
      ...makeParams(),
      messages: originalMessages,
      displayedMessages: originalMessages,
      dbConversation: { id: 'conversation-A' } as never,
    };
    useChatStore.setState({ currentThreadId: null });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    let submission!: Promise<void>;
    act(() => {
      submission = result.current.handleSubmit('cancel this turn');
    });
    expect(workspaceService.createThread).toHaveBeenCalledOnce();

    act(() => result.current.handleStop());
    await act(async () => {
      finishThreadCreation({ id: 'thread-new', title: 'cancel this turn' });
      await submission;
    });

    expect(streamMessageMock).not.toHaveBeenCalled();
    expect(params.setMessages).toHaveBeenLastCalledWith(originalMessages);
    expect(result.current.input).toBe('cancel this turn');
    expect(result.current.isLoading).toBe(false);
  });
});
