import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
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
const streamConfirmMock = vi.fn().mockResolvedValue(undefined);
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: (...a: unknown[]) => streamMessageMock(...a),
    streamConfirm: (...a: unknown[]) => streamConfirmMock(...a),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

type Cb = {
  onConfirmation: (t: string, c: Record<string, unknown>) => void;
  onDone: (p?: unknown) => void;
};

function makeParams(setMessages: (m: unknown) => void) {
  useChatStore.setState({ currentThreadId: 'thread-A' });
  return {
    messages: [] as ChatPageMessage[],
    displayedMessages: [] as ChatPageMessage[],
    setMessages,
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

describe('useChatStreaming in-band HITL approval', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('synthesizes an in-band approval message, and handleConfirmation routes to streamConfirm', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    let current: ChatPageMessage[] = [];
    const setMessages = vi.fn((m: unknown) => {
      current =
        typeof m === 'function'
          ? (m as (p: ChatPageMessage[]) => ChatPageMessage[])(current)
          : (m as ChatPageMessage[]);
    });

    streamMessageMock.mockImplementation((_r: unknown, cb: Cb) => {
      cb.onConfirmation('agent-thread-1', {
        tool_name: 'ingest_arxiv_papers',
        tool_args: { paper_ids: ['2605.1'] },
      });
      cb.onDone({});
      return Promise.resolve();
    });

    const params = makeParams(setMessages);
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('ingest these');
    });

    // The gate is surfaced as an in-band approval message in the transcript;
    // convertMessage turns pendingApproval into the real-`approval` tool part
    // that HitlApprovalToolUI renders (its respondToApproval routes through the
    // runtime adapter's onRespondToToolApproval → onApproval=handleConfirmation).
    const approvalMsg = current.find((m) => m.pendingApproval);
    expect(approvalMsg?.pendingApproval?.toolName).toBe('ingest_arxiv_papers');

    // handleConfirmation is exactly the onApproval target the adapter invokes;
    // approving must drive the hardened confirm flow (streamConfirm).
    await act(async () => {
      await result.current.handleConfirmation(true);
    });
    expect(streamConfirmMock).toHaveBeenCalledTimes(1);
    expect(streamConfirmMock.mock.calls[0][0]).toMatchObject({
      confirmed: true,
    });
  });
});

describe('the approval card survives the stream ending', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // The live incident: "Start a project about rag testing" raised a HITL
  // interrupt server-side, the SSE stream ended, and the user saw nothing —
  // no card, composer locked, Stop doing nothing. They re-sent twice and each
  // retry discarded the interrupt ("Abandoned HITL interrupt silently
  // dropped"). Two user rows, no assistant row.
  //
  // The existing test above passes on the broken code because it calls
  // onConfirmation and onDone synchronously: React never commits between
  // them, so the effect that appends the approval message hasn't run yet when
  // the unwind replaces the array. The real stream yields the confirmation
  // frame, awaits a Redis round-trip, then closes — which is a real gap.
  it('keeps the approval message when the stream closes after a commit', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    let current: ChatPageMessage[] = [];
    const setMessages = vi.fn((m: unknown) => {
      current =
        typeof m === 'function'
          ? (m as (p: ChatPageMessage[]) => ChatPageMessage[])(current)
          : (m as ChatPageMessage[]);
    });

    streamMessageMock.mockImplementation(async (_r: unknown, cb: Cb) => {
      cb.onConfirmation('agent-thread-1', {
        tool_name: 'create_project',
        tool_args: { name: 'rag testing' },
      });
      // Let React flush the approval effect before the stream unwinds —
      // this is the window the production SSE path leaves open.
      await new Promise((r) => setTimeout(r, 0));
      cb.onDone({});
    });

    const params = makeParams(setMessages);
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('start a project about rag testing');
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(
      current.filter((m) => m.pendingApproval).length,
      'the approval card must not be deleted by the stream unwind — without ' +
        'it the user has a locked composer and no way to answer'
    ).toBe(1);
  });

  it('handleStop clears a pending confirmation so the composer unlocks', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    let current: ChatPageMessage[] = [];
    const setMessages = vi.fn((m: unknown) => {
      current =
        typeof m === 'function'
          ? (m as (p: ChatPageMessage[]) => ChatPageMessage[])(current)
          : (m as ChatPageMessage[]);
    });

    streamMessageMock.mockImplementation(async (_r: unknown, cb: Cb) => {
      cb.onConfirmation('agent-thread-1', {
        tool_name: 'create_project',
        tool_args: { name: 'rag testing' },
      });
      cb.onDone({});
    });

    const params = makeParams(setMessages);
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('start a project');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    await act(async () => {
      result.current.handleStop();
    });

    expect(
      result.current.pendingConfirmation,
      'ChatSurface keeps isBusy true while this is set, so Stop must clear it'
    ).toBeNull();
  });
});

describe('a failed Approve keeps the gate', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // The `finally` cleared pendingConfirmation unconditionally, so a 500 or a
  // dropped connection on POST /agent/stream/confirm discarded the gate while
  // the backend graph stayed interrupted. The card vanished, the composer
  // unlocked, and the only remaining move — retyping — is what discards the
  // interrupt server-side ("Abandoned HITL interrupt silently dropped").
  it('retains pendingConfirmation when the confirm request throws', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');

    let current: ChatPageMessage[] = [];
    const setMessages = vi.fn((m: unknown) => {
      current =
        typeof m === 'function'
          ? (m as (p: ChatPageMessage[]) => ChatPageMessage[])(current)
          : (m as ChatPageMessage[]);
    });

    streamMessageMock.mockImplementation(async (_r: unknown, cb: Cb) => {
      cb.onConfirmation('agent-thread-1', {
        tool_name: 'create_project',
        tool_args: { name: 'rag testing' },
      });
      cb.onDone({});
    });
    streamConfirmMock.mockRejectedValue(new Error('network down'));

    const params = makeParams(setMessages);
    const { result } = renderHook(() => useChatStreaming(params), { wrapper });

    await act(async () => {
      await result.current.handleSubmit('start a project');
    });
    expect(result.current.pendingConfirmation).not.toBeNull();

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    expect(
      result.current.pendingConfirmation,
      'the graph is still interrupted — dropping the gate strands it with no ' +
        'way to answer, and retyping discards the interrupt server-side'
    ).not.toBeNull();
  });
});
