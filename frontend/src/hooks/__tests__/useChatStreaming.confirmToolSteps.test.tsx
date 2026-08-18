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

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { workspaceService } from '@/services/workspaceService';

type StreamCallbacks = {
  onToken: (t: string) => void;
  onToolStart: (tool: string, args?: Record<string, unknown>) => void;
  onToolEnd: (tool: string, result: string, isError: boolean) => void;
  onRagContext: (contexts: Array<Record<string, unknown>>) => void;
  onPlan: (steps: Array<Record<string, unknown>>, reasoning: string) => void;
  onConfirmation: (
    threadId: string,
    confirmation: Record<string, unknown>
  ) => void;
  onDone: (p?: unknown) => void;
};

function makeParams() {
  useChatStore.setState({ currentThreadId: 'thread-A' });
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

/**
 * Inspect only COMMITTED assistant messages across the mocked setMessages
 * calls. The hook always adds a transient streaming placeholder
 * (`isStreaming`) at turn start and mirrors the active HITL gate via a
 * functional `setMessages((prev) => …)` updater (P4 in-band approval) —
 * neither is a committed turn, so both are filtered out. The functional
 * updater is a bare vi.fn() that never applies, so non-array args are skipped.
 */
function committedAssistantMessages(
  setMessages: ReturnType<typeof vi.fn>
): ChatPageMessage[] {
  return setMessages.mock.calls
    .map((c) => c[0])
    .filter((arg): arg is ChatPageMessage[] => Array.isArray(arg))
    .flatMap((arr) => arr)
    .filter(
      (m) => m.role === 'assistant' && !m.isStreaming && !m.pendingApproval
    );
}

describe('useChatStreaming HITL confirm tool steps', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockReset();
    vi.mocked(workspaceService.listMessages).mockResolvedValue({
      messages: [],
      has_more: false,
    } as never);
  });

  it('tracks live streamingSteps during the confirm stream and commits toolExecutions', async () => {
    // Main stream: one settled tool, then interrupt for confirmation.
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onToolStart('summarize_document', { document_id: 'doc-1' });
        cb.onToolEnd('summarize_document', 'summary text', false);
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );

    const stepsDuringConfirmStream: unknown[][] = [];
    streamConfirmMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onToolStart('ingest_arxiv_papers', { paper_ids: ['2605.1'] });
        stepsDuringConfirmStream.push([
          ...useChatStore.getState().streamingSteps,
        ]);
        cb.onToolEnd('ingest_arxiv_papers', 'ingested', false);
        cb.onToken('done ingesting');
        cb.onDone({
          assistant_message_id: 'confirm-assistant-1',
          client_message_id: 'confirm-runtime-1',
          tool_executions: [
            {
              id: 't1',
              tool_name: 'summarize_document',
              tool_display_name: 'Summarize Document',
              args: { document_id: 'doc-1' },
              status: 'completed',
              result: { message: 'summary text' },
              duration_ms: 1234,
            },
            {
              id: 't2',
              tool_name: 'ingest_arxiv_papers',
              tool_display_name: 'Ingest Arxiv Papers',
              args: { paper_ids: ['2605.1'] },
              status: 'completed',
              result: { message: 'ingested' },
              duration_ms: 5678,
            },
          ],
        });
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const actualRefresh = useChatStore.getState().refreshMessages;
    const refreshSpy = vi.fn(actualRefresh);
    useChatStore.setState({ refreshMessages: refreshSpy });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('summarize and ingest');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();
    // Pre-interrupt settled step is carried on the pending confirmation.
    expect(result.current.pendingConfirmation?.steps).toMatchObject([
      { tool: 'summarize_document', status: 'done' },
    ]);
    refreshSpy.mockClear();

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        persistedId: 'confirm-assistant-1',
        runtimeId: 'confirm-runtime-1',
        diagnostic: expect.objectContaining({
          terminalReason: 'confirmation-approved',
        }),
      })
    );
    useChatStore.setState({ refreshMessages: actualRefresh });

    // Live: streamingSteps held both the carried step and the running tool.
    expect(stepsDuringConfirmStream[0]).toMatchObject([
      { tool: 'summarize_document', status: 'done' },
      { tool: 'ingest_arxiv_papers', status: 'running' },
    ]);

    // Committed: the assistant message carries the full turn's tools,
    // reconciled from the done payload's full-fidelity executions (real
    // durations from the graph state, not the live summaries).
    const committed = committedAssistantMessages(params.setMessages);
    expect(committed[committed.length - 1]).toMatchObject({
      role: 'assistant',
      content: 'done ingesting',
      toolExecutions: [
        { tool: 'summarize_document', status: 'done', durationMs: 1234 },
        { tool: 'ingest_arxiv_papers', status: 'done', durationMs: 5678 },
      ],
      metadata: {
        toolsUsed: ['Summarize Document', 'Ingest Arxiv Papers'],
        responseTimeMs: expect.any(Number),
      },
    });

    // Streaming state fully unwound.
    expect(useChatStore.getState().streamingSteps).toEqual([]);
    // Activity rail closed out — a confirmed turn must not stay "running"
    // forever (round-3 M1). The run is keyed by the workspace thread id.
    const run = useAgentActivityStore.getState().runs['thread-A'];
    expect(run?.state).toBe('done');
  });

  it('carries pre-interrupt plan + citations into the committed confirm message', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onPlan(
          [
            {
              step: 1,
              description: 'Ingest the papers',
              tool: 'ingest_arxiv_papers',
            },
          ],
          'Ingest first, then summarize.'
        );
        cb.onRagContext([{ document_id: 'doc-1', content: 'ctx' }]);
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );
    streamConfirmMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
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
    expect(result.current.pendingConfirmation?.planReasoning).toBe(
      'Ingest first, then summarize.'
    );
    expect(result.current.pendingConfirmation?.citations).toHaveLength(1);

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    const committed = committedAssistantMessages(params.setMessages);
    expect(committed[committed.length - 1]).toMatchObject({
      role: 'assistant',
      content: 'confirmed answer',
      plan: [{ description: 'Ingest the papers' }],
      planReasoning: 'Ingest first, then summarize.',
      citations: [expect.any(Object)],
    });
  });

  it('re-arms pendingConfirmation on a nested interrupt instead of dropping it', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );
    streamConfirmMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onToolStart('ingest_arxiv_papers', {});
        cb.onToolEnd('ingest_arxiv_papers', 'ok', false);
        // Backend hits a SECOND destructive tool and ends without done.
        cb.onConfirmation('agent-thread-1', { tool: 'create_note' });
        return Promise.resolve();
      }
    );

    const params = makeParams();
    const actualRefresh = useChatStore.getState().refreshMessages;
    const refreshSpy = vi.fn(actualRefresh);
    useChatStore.setState({ refreshMessages: refreshSpy });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest then note');
    });
    const userRuntimeId = result.current.pendingConfirmation?.userRuntimeId;
    expect(userRuntimeId).toBeDefined();
    refreshSpy.mockClear();
    await act(async () => {
      await result.current.handleConfirmation(true);
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
    useChatStore.setState({ refreshMessages: actualRefresh });

    // The banner is re-armed for the nested action, carrying the settled
    // steps from the first resume.
    expect(result.current.pendingConfirmation).toMatchObject({
      threadId: 'agent-thread-1',
      confirmation: { tool: 'create_note' },
      steps: [{ tool: 'ingest_arxiv_papers', status: 'done' }],
    });
    // Nothing was committed for the incomplete turn — the transient streaming
    // placeholder and P4 approval-mirror updaters are excluded by the helper.
    const committed = committedAssistantMessages(params.setMessages);
    expect(committed).toEqual([]);
  });

  it('commits the partial answer tagged stopped when the user aborts the confirm stream', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );
    let releaseConfirm!: () => void;
    let confirmCb!: StreamCallbacks;
    streamConfirmMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) =>
        new Promise<void>((resolve) => {
          confirmCb = cb;
          releaseConfirm = resolve;
        })
    );

    const params = makeParams();
    const actualRefresh = useChatStore.getState().refreshMessages;
    const refreshSpy = vi.fn(actualRefresh);
    useChatStore.setState({ refreshMessages: refreshSpy });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    const assistantRuntimeId =
      result.current.pendingConfirmation?.assistantRuntimeId;
    expect(assistantRuntimeId).toBeDefined();
    refreshSpy.mockClear();

    let confirmPromise!: Promise<void>;
    act(() => {
      confirmPromise = result.current.handleConfirmation(true);
    });
    // Partial tokens arrive, then the user hits Stop (abort → no onDone).
    await act(async () => {
      confirmCb.onToken('partial resumed answer');
      result.current.handleStop();
      releaseConfirm();
      await confirmPromise;
    });

    // The confirm stream commits the partial answer tagged `stopped` — the
    // last committed assistant message (functional P4 updaters are excluded).
    const committed = committedAssistantMessages(params.setMessages);
    expect(committed[committed.length - 1]).toMatchObject({
      role: 'assistant',
      content: 'partial resumed answer',
      metadata: { stopped: true },
    });
    expect(refreshSpy).toHaveBeenCalledWith(
      'thread-A',
      expect.objectContaining({
        persistedId: undefined,
        runtimeId: assistantRuntimeId,
        diagnostic: expect.objectContaining({
          terminalReason: 'confirmation-stopped',
        }),
      })
    );
    useChatStore.setState({ refreshMessages: actualRefresh });
  });

  it('CX1: a synchronous double-click on Approve only fires streamConfirm once', async () => {
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: StreamCallbacks) => {
        cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
        cb.onDone({});
        return Promise.resolve();
      }
    );
    let releaseConfirm!: () => void;
    streamConfirmMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          releaseConfirm = resolve;
        })
    );

    const params = makeParams();
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    // Two Approve calls in the same tick, before the first streamConfirm
    // call has resolved — mirrors a fast double-click. The second call
    // must be blocked client-side (confirmLockRef), not just deduped by
    // the server-side claim (CX1 backend fix).
    let p1!: Promise<void>;
    let p2!: Promise<void>;
    act(() => {
      p1 = result.current.handleConfirmation(true);
      p2 = result.current.handleConfirmation(true);
    });

    expect(streamConfirmMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      releaseConfirm();
      await Promise.all([p1, p2]);
    });

    // Still exactly one call after both promises settle.
    expect(streamConfirmMock).toHaveBeenCalledTimes(1);
    // The lock released so a later, legitimate confirmation isn't stuck.
    expect(result.current.isConfirming).toBe(false);
  });
});
