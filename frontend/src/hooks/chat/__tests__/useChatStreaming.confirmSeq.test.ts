// The resume cursor must keep advancing while a HITL-confirmed turn streams.
// The primary stream wires `onSeq` (SSE `id:` line -> activity store), but the
// confirm/resume call omitted it, so the cursor stayed frozen at whatever seq
// the pre-interrupt turn reached. A disconnect during the resumed turn then
// replayed GET /stream/resume from that stale position.
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { UseChatStreamingParams } from '@/hooks/chat/useChatStreaming';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

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

const resumeStreamMock = vi.fn();
const streamConfirmMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: vi.fn(),
    streamConfirm: (...args: unknown[]) => streamConfirmMock(...args),
    resumeStream: (...args: unknown[]) => resumeStreamMock(...args),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    listMessages: vi.fn().mockResolvedValue({ messages: [], has_more: false }),
  },
}));

const THREAD_ID = 'thread-A';
const CONFIRMATION = {
  tool_name: 'create_note',
  tool_args: { title: 'parked' },
};
const RESUMED_SEQ = 42;

function makeParams(): UseChatStreamingParams {
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

describe('useChatStreaming confirm-path resume cursor', () => {
  beforeEach(() => {
    resumeStreamMock.mockReset();
    streamConfirmMock.mockReset();
    // Server holds a parked interrupt, so the cold-load probe arms the gate.
    resumeStreamMock.mockImplementation(
      async (
        threadId: string,
        _after: number,
        cb: {
          onConfirmation?: (t: string, c: Record<string, unknown>) => void;
        }
      ) => {
        cb.onConfirmation?.(threadId, CONFIRMATION);
        return { resumed: true };
      }
    );
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({
      currentThreadId: THREAD_ID,
      isStreaming: false,
      streamingThreadId: null,
    });
  });

  it('advances the resume cursor from frames streamed after approval', async () => {
    streamConfirmMock.mockImplementation(
      async (_body: unknown, cb: { onSeq?: (seq: number) => void }) => {
        cb.onSeq?.(RESUMED_SEQ);
        return undefined;
      }
    );

    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await waitFor(() =>
      expect(result.current.pendingConfirmation).not.toBeNull()
    );

    // The interrupt came out of a live turn, so the thread has a run record —
    // setStreamSeq is a no-op without one.
    act(() => {
      useAgentActivityStore.getState().startRun(THREAD_ID, 'NOUS', 'parked');
    });

    await act(async () => {
      await result.current.handleConfirmation(true);
    });

    expect(streamConfirmMock).toHaveBeenCalledTimes(1);
    const callbacks = streamConfirmMock.mock.calls[0]?.[1] as {
      onSeq?: unknown;
    };
    expect(
      typeof callbacks.onSeq,
      'confirm path must pass onSeq like the primary stream does'
    ).toBe('function');

    // onSeq is rAF-batched (same as the primary path), so the store settles a
    // frame later.
    await waitFor(() =>
      expect(
        useAgentActivityStore.getState().runs[THREAD_ID]?.streamSeq
      ).toBe(RESUMED_SEQ)
    );
  });
});
