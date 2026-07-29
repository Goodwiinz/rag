/**
 * Deterministic interleaving tests for the seven chat store/hook guard groups
 * catalogued in docs/testing/chat-mutation-checks.md. Where a guard lives in a
 * store slice we drive `useChatStore` directly with the createDeferred/
 * runInterleaving scheduler (no timers, no randomness — the schedule fixes the
 * order). Where a guard lives in `useChatStreaming` we drive it through
 * `renderHook` + `act()` exactly like the existing hook suites, because
 * runInterleaving is not React-`act`-aware; `act()` is itself the deterministic
 * microtask driver there. createDeferred backs the in-flight service promises in
 * both styles so every settle happens on the test's schedule.
 *
 * Correctness discipline (from review): every last-writer / stale-drop row also
 * proves the stale continuation actually RAN — otherwise a fixed microtask drain
 * could false-pass by never resuming it. For the store request-identity guard the
 * side-channel is the superseded refresh's `false` return (it entered the try,
 * awaited, hit the identity check, returned false). For the reconciliation guard
 * it is the `[ChatReconciliationInvariant]` console.warn. For the thread-scope
 * turn guard it is the thread-A reconciliation `listMessages` call that fires even
 * though `setMessages` was suppressed.
 *
 * Documented gaps:
 * - Group 4b's core is a pure synchronous predicate (`confirmationBelongsToThread`)
 *   with no async surface to schedule, so its table is a decision table rather than
 *   an interleaving; the async path (click after a mid-flight thread switch) is
 *   covered by the hook interleaving in the same block.
 * - Group 4a proves the confirm lock RELEASES on both settle paths (isConfirming
 *   returns to false) but not "admits the next confirm", because a completed
 *   confirmation clears pendingConfirmation and would confound the follow-up call.
 *   The unconfounded "single-flight admits a legit next operation" proof lives in
 *   group 5 (submit), which shares the same finally-release lock structure.
 * - Group 6's guard (`isThreadSwitchPending`) is a pure snapshot selector; the
 *   interleavings that PRODUCE its input states are covered in
 *   useChatSession.threadSwitchBleed.test.tsx. Here we pin the gate's decision
 *   under each such outcome, so there is no stale continuation to observe.
 */
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactElement, type ReactNode } from 'react';
import { enableMapSet } from 'immer';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import {
  createDeferred,
  runInterleaving,
  type Deferred,
  type Step,
} from '../deferredScheduler';
import {
  ChatMessage,
  ChatMessageListResponse,
  MessageRole,
} from '@/types/workspace';

enableMapSet();

// ---- Mocks (superset needed by the hook-driven groups; the store-driven
// groups only touch workspaceService.listMessages). ----
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
    deleteThread: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import {
  confirmationBelongsToThread,
  useChatStreaming,
  type PendingConfirmation,
  type UseChatStreamingParams,
} from '@/hooks/chat/useChatStreaming';
import { isThreadSwitchPending } from '@/components/chat/shared/cloudMessageView';

const listMessagesMock = vi.mocked(workspaceService.listMessages);
const store = (): ReturnType<typeof useChatStore.getState> =>
  useChatStore.getState();

// ---- Shared fixtures ----
function wrapper({ children }: { children: ReactNode }): ReactElement {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

function msg(
  id: string,
  threadId = 'thread-a',
  clientMessageId?: string
): ChatMessage {
  return {
    id,
    thread_id: threadId,
    content: `message ${id}`,
    role: MessageRole.USER,
    token_count: 0,
    citations: [],
    attachments: [],
    client_message_id: clientMessageId ?? null,
    created_at: `2026-07-15T00:00:${id.replace(/\D/g, '').padStart(2, '0')}Z`,
    updated_at: `2026-07-15T00:00:${id.replace(/\D/g, '').padStart(2, '0')}Z`,
  };
}

function response(
  messages: ChatMessage[],
  hasMore = false
): ChatMessageListResponse {
  return { messages, total: messages.length, page: 1, limit: 50, has_more: hasMore };
}

/** Hand listMessages a queue of deferreds, one per call in start order. */
function queueListMessages(
  ...deferreds: Deferred<ChatMessageListResponse>[]
): void {
  let index = 0;
  listMessagesMock.mockImplementation(
    () => (deferreds[index++]?.promise ?? new Promise(() => {})) as never
  );
}

// Only the fields useChatStreaming actually reads; the hook resolves the active
// thread from useChatStore, not from params. setMessages is kept as a Mock so
// the thread-scope group can inspect its calls.
function makeStreamingParams(): UseChatStreamingParams & { setMessages: Mock } {
  return {
    messages: [],
    displayedMessages: [],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    dbConversation: null,
    enableRAG: false,
  };
}

type StreamCallbacks = {
  onToken: (t: string) => void;
  onToolStart: (tool: string, args?: Record<string, unknown>) => void;
  onToolEnd: (tool: string, result: string, isError: boolean) => void;
  onConfirmation: (
    threadId: string,
    confirmation: Record<string, unknown>
  ) => void;
  onDone: (p?: unknown) => void;
};

beforeEach(() => {
  streamMessageMock.mockReset();
  streamConfirmMock.mockReset();
  listMessagesMock.mockReset();
  // Hook groups reconcile via a background newest-page fetch; keep it empty and
  // instantaneous. Store groups override this per-test with deferred queues.
  listMessagesMock.mockResolvedValue(response([]) as never);
  act(() => store().reset());
  // reset() already replays initialState (isStreaming: false), so this is
  // redundant with it; kept as an isolation belt-and-suspenders in case a hook
  // turn left mid-stream (single-flight rows deliberately never emit onDone)
  // leaves the streaming slice dirty, so each row starts from a quiescent composer.
  useChatStore.setState({ isStreaming: false } as never);
});

// ===========================================================================
// 1. Stale-response rejection (REQUEST-IDENTITY) — messageSlice refreshMessages
//    guard `if (newestPageRequests.get(threadId) !== request) return false;`.
//    Store-driven via runInterleaving.
// ===========================================================================
describe('group 1 — stale-response rejection (request-identity)', () => {
  interface Scenario {
    steps: Step[];
    refs: Record<string, Promise<boolean>>;
    // The refresh that must commit its page (or null when every request is
    // dropped, e.g. the thread was cleared mid-flight).
    winner: string | null;
    stale: string[];
    finalIds: string[] | undefined;
  }

  const rows: Array<{ name: string; build: () => Scenario }> = [
    {
      name: 'classic stale: A-start, B-start, B-resolve, A-resolve → B kept, stale A ran',
      build: () => {
        const a = createDeferred<ChatMessageListResponse>();
        const b = createDeferred<ChatMessageListResponse>();
        queueListMessages(a, b);
        const refs: Record<string, Promise<boolean>> = {};
        return {
          refs,
          winner: 'b',
          stale: ['a'],
          finalIds: ['m2'],
          steps: [
            { kind: 'run', fn: () => void (refs.a = store().refreshMessages('thread-a')) },
            { kind: 'run', fn: () => void (refs.b = store().refreshMessages('thread-a')) },
            { kind: 'resolve', deferred: b, value: response([msg('m2')]) },
            { kind: 'resolve', deferred: a, value: response([msg('m1')]) },
          ],
        };
      },
    },
    {
      name: 're-entry A→B→A′: three same-thread refreshes, only the newest commits',
      build: () => {
        const a = createDeferred<ChatMessageListResponse>();
        const b = createDeferred<ChatMessageListResponse>();
        const c = createDeferred<ChatMessageListResponse>();
        queueListMessages(a, b, c);
        const refs: Record<string, Promise<boolean>> = {};
        return {
          refs,
          winner: 'c',
          stale: ['a', 'b'],
          finalIds: ['m3'],
          steps: [
            { kind: 'run', fn: () => void (refs.a = store().refreshMessages('thread-a')) },
            { kind: 'run', fn: () => void (refs.b = store().refreshMessages('thread-a')) },
            { kind: 'run', fn: () => void (refs.c = store().refreshMessages('thread-a')) },
            { kind: 'resolve', deferred: c, value: response([msg('m3')]) },
            { kind: 'resolve', deferred: b, value: response([msg('m2')]) },
            { kind: 'resolve', deferred: a, value: response([msg('m1')]) },
          ],
        };
      },
    },
    {
      name: 'reject-then-resolve: stale A rejects, newer B resolves → B kept, stale A dropped',
      build: () => {
        const a = createDeferred<ChatMessageListResponse>();
        const b = createDeferred<ChatMessageListResponse>();
        queueListMessages(a, b);
        const refs: Record<string, Promise<boolean>> = {};
        return {
          refs,
          winner: 'b',
          stale: ['a'],
          finalIds: ['m2'],
          steps: [
            { kind: 'run', fn: () => void (refs.a = store().refreshMessages('thread-a')) },
            { kind: 'run', fn: () => void (refs.b = store().refreshMessages('thread-a')) },
            { kind: 'reject', deferred: a, error: new Error('stale network error') },
            { kind: 'resolve', deferred: b, value: response([msg('m2')]) },
          ],
        };
      },
    },
    {
      name: 'clear mid-flight: A-start, clearThread, A-resolve → response dropped, cache gone',
      build: () => {
        const a = createDeferred<ChatMessageListResponse>();
        queueListMessages(a);
        const refs: Record<string, Promise<boolean>> = {};
        return {
          refs,
          winner: null,
          stale: ['a'],
          finalIds: undefined,
          steps: [
            { kind: 'run', fn: () => void (refs.a = store().refreshMessages('thread-a')) },
            { kind: 'run', fn: () => store().clearThread('thread-a') },
            { kind: 'resolve', deferred: a, value: response([msg('m1')]) },
          ],
        };
      },
    },
  ];

  it.each(rows)('$name', async ({ build }) => {
    const s = build();
    await runInterleaving(s.steps);

    // Stale continuations RAN and were dropped: `false` proves each entered the
    // try, awaited, and hit the identity guard — not merely that state is clean.
    for (const label of s.stale) {
      await expect(s.refs[label]).resolves.toBe(false);
    }
    if (s.winner) {
      await expect(s.refs[s.winner]).resolves.toBe(true);
    }
    if (s.finalIds === undefined) {
      expect(store().messages['thread-a']).toBeUndefined();
    } else {
      expect(store().messages['thread-a'].map((m) => m.id)).toEqual(s.finalIds);
    }
  });
});

// ===========================================================================
// 2. Expectation reconciliation (expectationMet) — messageSlice refreshMessages
//    marks freshness stale when the expected terminal row is missing from the
//    fetched page. Store-driven.
// ===========================================================================
describe('group 2 — expectation reconciliation (expectationMet)', () => {
  const diagnostic = {
    terminalReason: 'done' as const,
    localCount: 2,
    completedInBackground: false,
  };

  const rows: Array<{
    name: string;
    expected: { persistedId?: string; runtimeId?: string } | undefined;
    page: ChatMessage[];
    result: boolean;
    freshness: 'fresh' | 'stale';
    warns: boolean;
  }> = [
    {
      name: 'persistedId missing from page → stale, returns false, warns',
      expected: { persistedId: 'missing-id' },
      page: [msg('m1')],
      result: false,
      freshness: 'stale',
      warns: true,
    },
    {
      name: 'runtimeId missing from page → stale, returns false, warns',
      expected: { runtimeId: 'missing-runtime' },
      page: [msg('m1')],
      result: false,
      freshness: 'stale',
      warns: true,
    },
    {
      name: 'persistedId present → fresh, returns true, no warn',
      expected: { persistedId: 'm1' },
      page: [msg('m1')],
      result: true,
      freshness: 'fresh',
      warns: false,
    },
    {
      name: 'runtimeId matched via client_message_id → fresh, returns true, no warn',
      expected: { runtimeId: 'runtime-1' },
      page: [msg('m1', 'thread-a', 'runtime-1')],
      result: true,
      freshness: 'fresh',
      warns: false,
    },
    {
      name: 'no expectation → fresh, returns true, no warn',
      expected: undefined,
      page: [msg('m1')],
      result: true,
      freshness: 'fresh',
      warns: false,
    },
  ];

  it.each(rows)('$name', async ({ expected, page, result, freshness, warns }) => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const req = createDeferred<ChatMessageListResponse>();
    queueListMessages(req);
    store().markMessagesStale('thread-a');

    let refresh!: Promise<boolean>;
    await runInterleaving([
      {
        kind: 'run',
        fn: () =>
          void (refresh = store().refreshMessages(
            'thread-a',
            expected ? { ...expected, diagnostic } : undefined
          )),
      },
      { kind: 'resolve', deferred: req, value: response(page) },
    ]);

    await expect(refresh).resolves.toBe(result);
    expect(store().messageFreshness['thread-a']).toBe(freshness);
    // The invariant warn is the side-channel: it proves the reconciliation
    // continuation ran all the way to the stale-decision branch.
    if (warns) {
      expect(warn).toHaveBeenCalledWith(
        '[ChatReconciliationInvariant]',
        expect.objectContaining({
          threadId: 'thread-a',
          failureKind: 'expected-message-missing',
          freshness: 'stale',
        })
      );
    } else {
      expect(warn).not.toHaveBeenCalled();
    }
    warn.mockRestore();
  });

  it('superseded expectation refresh returns false without warning, newer page commits fresh', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const older = createDeferred<ChatMessageListResponse>();
    const newer = createDeferred<ChatMessageListResponse>();
    queueListMessages(older, newer);

    let first!: Promise<boolean>;
    let second!: Promise<boolean>;
    await runInterleaving([
      {
        kind: 'run',
        fn: () =>
          void (first = store().refreshMessages('thread-a', {
            runtimeId: 'runtime-1',
            diagnostic,
          })),
      },
      { kind: 'run', fn: () => void (second = store().refreshMessages('thread-a')) },
      { kind: 'resolve', deferred: newer, value: response([msg('m2')]) },
      { kind: 'resolve', deferred: older, value: response([msg('m1')]) },
    ]);

    await expect(first).resolves.toBe(false);
    await expect(second).resolves.toBe(true);
    // Superseded reconciliation must short-circuit before the invariant warn.
    expect(warn).not.toHaveBeenCalled();
    expect(store().messageFreshness['thread-a']).toBe('fresh');
    warn.mockRestore();
  });
});

// ===========================================================================
// 3. Thread-scope turn gating (isTurnDisplayed) — useChatStreaming runStreamTurn
//    gates every committing setMessages on the turn's origin thread still being
//    displayed. Hook-driven.
// ===========================================================================
describe('group 3 — thread-scope turn gating (isTurnDisplayed)', () => {
  const rows: Array<{ name: string; switchMidStream: boolean }> = [
    {
      name: 'switch A→B mid-stream: completion is suppressed but thread A still reconciles',
      switchMidStream: true,
    },
    {
      name: 'no switch (control): completion commits the assistant answer',
      switchMidStream: false,
    },
  ];

  it.each(rows)('$name', async ({ switchMidStream }) => {
    let finish!: () => void;
    streamMessageMock.mockImplementation((_req: unknown, cb: StreamCallbacks) => {
      cb.onToken('hello from thread A');
      cb.onDone({});
      return new Promise<void>((resolve) => {
        finish = resolve;
      });
    });

    const params = makeStreamingParams();
    useChatStore.setState({ currentThreadId: 'thread-A' });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    let submit!: Promise<void>;
    act(() => {
      submit = result.current.handleSubmit('question for thread A');
    });

    if (switchMidStream) {
      useChatStore.setState({ currentThreadId: 'thread-B' });
    }
    params.setMessages.mockClear(); // ignore the optimistic user-bubble write

    await act(async () => {
      finish();
      await submit;
    });

    if (switchMidStream) {
      // Guard held: the background turn did not write into thread B's transcript…
      expect(params.setMessages).not.toHaveBeenCalled();
      // …yet the completion continuation RAN — it reconciled thread A's page.
      expect(listMessagesMock).toHaveBeenCalledWith(
        'thread-A',
        expect.objectContaining({ order: 'desc' })
      );
    } else {
      const calls = params.setMessages.mock.calls;
      const lastArg = calls[calls.length - 1][0] as Array<{
        role: string;
        content: string;
      }>;
      expect(lastArg[lastArg.length - 1]).toMatchObject({
        role: 'assistant',
        content: 'hello from thread A',
      });
    }
  });
});

// ===========================================================================
// 4a. HITL confirm idempotency (confirmLockRef) — useChatStreaming blocks a
//     synchronous double Approve; the finally releases the lock on both the
//     resolve and reject settle paths. Hook-driven.
// ===========================================================================
describe('group 4a — HITL confirm idempotency (confirmLockRef)', () => {
  const rows: Array<{ name: string; settle: 'resolve' | 'reject' }> = [
    {
      name: 'double-click fires streamConfirm once; lock releases on resolve',
      settle: 'resolve',
    },
    {
      name: 'double-click fires streamConfirm once; lock releases on reject',
      settle: 'reject',
    },
  ];

  it.each(rows)('$name', async ({ settle }) => {
    streamMessageMock.mockImplementation((_req: unknown, cb: StreamCallbacks) => {
      cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
      cb.onDone({});
      return Promise.resolve();
    });
    let settleConfirm!: () => void;
    streamConfirmMock.mockImplementationOnce(
      () =>
        new Promise<void>((resolve, reject) => {
          settleConfirm =
            settle === 'resolve'
              ? () => resolve()
              : () => reject(new Error('confirm failed'));
        })
    );

    const params = makeStreamingParams();
    useChatStore.setState({ currentThreadId: 'thread-A' });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    // Two Approve clicks in the same tick, before the first streamConfirm
    // settles — the second must be blocked client-side by confirmLockRef.
    let p1!: Promise<void>;
    let p2!: Promise<void>;
    act(() => {
      p1 = result.current.handleConfirmation(true);
      p2 = result.current.handleConfirmation(true);
    });
    expect(streamConfirmMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      settleConfirm();
      await Promise.allSettled([p1, p2]);
    });

    // Still one call, and the lock released (isConfirming back to false) so the
    // UI is not wedged — proven on both the resolve and reject settle paths.
    expect(streamConfirmMock).toHaveBeenCalledTimes(1);
    expect(result.current.isConfirming).toBe(false);
  });
});

// ===========================================================================
// 4b. HITL confirm thread-scope (confirmationBelongsToThread) — a confirmation
//     must only resume/render against its own thread. Pure predicate table plus
//     a hook interleaving for the click-after-switch path.
// ===========================================================================
describe('group 4b — HITL confirm thread-scope (confirmationBelongsToThread)', () => {
  const pending = (workspaceThreadId: string): PendingConfirmation => ({
    threadId: 'agent-thread-1',
    workspaceThreadId,
    confirmation: {},
  });

  const predicateRows: Array<{
    name: string;
    pending: PendingConfirmation | null;
    displayed: string | null;
    expected: boolean;
  }> = [
    { name: 'same displayed thread → belongs', pending: pending('t-1'), displayed: 't-1', expected: true },
    { name: 'different displayed thread → rejected', pending: pending('t-1'), displayed: 't-2', expected: false },
    { name: 'new-chat (null) matches empty workspace thread', pending: pending(''), displayed: null, expected: true },
    { name: 'new-chat (null) rejects a real workspace thread', pending: pending('t-1'), displayed: null, expected: false },
    { name: 'null confirmation → rejected', pending: null, displayed: 't-1', expected: false },
  ];

  it.each(predicateRows)('predicate: $name', ({ pending: p, displayed, expected }) => {
    expect(confirmationBelongsToThread(p, displayed)).toBe(expected);
  });

  const hookRows: Array<{ name: string; switchAway: boolean; expectStreamConfirm: boolean }> = [
    {
      name: 'interrupt on A, switch to B, then Approve → streamConfirm blocked',
      switchAway: true,
      expectStreamConfirm: false,
    },
    {
      name: 'interrupt on A, stay on A, then Approve → streamConfirm fires (control)',
      switchAway: false,
      expectStreamConfirm: true,
    },
  ];

  it.each(hookRows)('interleaving: $name', async ({ switchAway, expectStreamConfirm }) => {
    streamMessageMock.mockImplementation((_req: unknown, cb: StreamCallbacks) => {
      cb.onConfirmation('agent-thread-1', { tool: 'ingest_arxiv_papers' });
      cb.onDone({});
      return Promise.resolve();
    });
    streamConfirmMock.mockResolvedValue(undefined);

    const params = makeStreamingParams();
    useChatStore.setState({ currentThreadId: 'thread-A' });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    if (switchAway) {
      useChatStore.setState({ currentThreadId: 'thread-B' });
    }

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    expect(streamConfirmMock).toHaveBeenCalledTimes(expectStreamConfirm ? 1 : 0);
  });
});

// ===========================================================================
// 5. Submit single-flight (submitLockRef) — useChatStreaming blocks a
//    synchronous second handleSubmit while the first turn is in flight, then
//    admits a genuine later submit once the lock releases. Hook-driven.
// ===========================================================================
describe('group 5 — submit single-flight (submitLockRef)', () => {
  const rows: Array<{ name: string; settle: 'resolve' | 'reject' }> = [
    {
      name: 'double submit fires streamMessage once; a third legit submit is admitted after resolve',
      settle: 'resolve',
    },
    {
      name: 'double submit fires streamMessage once; a third legit submit is admitted after reject',
      settle: 'reject',
    },
  ];

  it.each(rows)('$name', async ({ settle }) => {
    // The turn settles immediately on its own settle path (resolve emits
    // onDone; reject throws). We don't hang the stream — the single-flight
    // window is the synchronous tick in which both handleSubmit calls run, so
    // submitLockRef alone decides the second call, no in-flight promise needed.
    streamMessageMock.mockImplementation((_req: unknown, cb: StreamCallbacks) => {
      if (settle === 'reject') return Promise.reject(new Error('stream failed'));
      cb.onToken('answer');
      cb.onDone({});
      return Promise.resolve();
    });

    const params = makeStreamingParams();
    useChatStore.setState({ currentThreadId: 'thread-A' });
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    // Two handleSubmit calls in the same tick — the second must be blocked.
    let p1!: Promise<void>;
    let p2!: Promise<void>;
    act(() => {
      p1 = result.current.handleSubmit('first message');
      p2 = result.current.handleSubmit('second message');
    });
    expect(streamMessageMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await Promise.allSettled([p1, p2]);
    });
    expect(streamMessageMock).toHaveBeenCalledTimes(1);
    expect(result.current.isLoading).toBe(false);

    // Single-flight is not a permanent latch: a genuine later submit reaches
    // streamMessage again, proving the lock released on this settle path.
    await act(async () => {
      await result.current.handleSubmit('later message').catch(() => {});
    });
    expect(streamMessageMock).toHaveBeenCalledTimes(2);
  });
});

// ===========================================================================
// 6. Loading-skeleton gate (isThreadSwitchPending) — pure snapshot selector.
//    Decision table over the interleaving OUTCOMES it must classify.
// ===========================================================================
describe('group 6 — loading-skeleton gate (isThreadSwitchPending)', () => {
  const rows: Array<{
    name: string;
    params: Parameters<typeof isThreadSwitchPending>[0];
    expected: boolean;
  }> = [
    {
      name: 'active thread cache-miss mid-load, nothing renderable → skeleton',
      params: {
        activeThreadId: 'thread-C',
        loadingThreadId: 'thread-C',
        localMessageCount: 0,
        storeMessageCount: 0,
      },
      expected: true,
    },
    {
      name: 'cached thread switch (store rows present) → no skeleton',
      params: {
        activeThreadId: 'thread-B',
        loadingThreadId: 'thread-B',
        localMessageCount: 0,
        storeMessageCount: 2,
      },
      expected: false,
    },
    {
      name: 'local optimistic/streaming turn present → no skeleton',
      params: {
        activeThreadId: 'thread-new',
        loadingThreadId: 'thread-new',
        localMessageCount: 1,
        storeMessageCount: 0,
      },
      expected: false,
    },
    {
      name: 'background refresh of a different thread → no skeleton',
      params: {
        activeThreadId: 'thread-A',
        loadingThreadId: 'thread-C',
        localMessageCount: 0,
        storeMessageCount: 0,
      },
      expected: false,
    },
    {
      name: 'no active thread → no skeleton',
      params: {
        activeThreadId: null,
        loadingThreadId: null,
        localMessageCount: 0,
        storeMessageCount: 0,
      },
      expected: false,
    },
  ];

  it.each(rows)('$name', ({ params, expected }) => {
    expect(isThreadSwitchPending(params)).toBe(expected);
  });
});
