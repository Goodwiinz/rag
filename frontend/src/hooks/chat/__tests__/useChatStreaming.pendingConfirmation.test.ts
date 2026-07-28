// A thread parked on a HITL interrupt must re-arm its approval gate after a
// reload. The activity store is in-memory, so a cold client has no run record
// and the resume effect can never fire — the user saw their message with no
// reply, no Approve/Deny card and an unlocked composer, re-sent, and parked a
// SECOND interrupt.
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

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

const resumeStreamMock = vi.fn();
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    streamMessage: vi.fn(),
    streamConfirm: vi.fn(),
    resumeStream: (...args: unknown[]) => resumeStreamMock(...args),
  },
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createThread: vi.fn(),
    listMessages: vi.fn().mockResolvedValue({ messages: [], has_more: false }),
  },
}));

const CONFIRMATION = {
  tool_name: 'create_project',
  tool_args: { name: 'rag testing' },
};

/** Server holds a parked interrupt: resume replays a single confirmation. */
function parkedInterrupt() {
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
}

function makeParams() {
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

async function renderStreaming() {
  const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
  const params = makeParams();
  return renderHook(() => useChatStreaming(params), { wrapper });
}

describe('useChatStreaming pending-confirmation probe (cold thread load)', () => {
  beforeEach(() => {
    resumeStreamMock.mockReset();
    resumeStreamMock.mockResolvedValue({ resumed: false });
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({
      currentThreadId: 'thread-A',
      isStreaming: false,
      streamingThreadId: null,
    });
  });

  it('re-arms the approval gate for a thread parked server-side', async () => {
    parkedInterrupt();
    const { result } = await renderStreaming();

    await waitFor(() =>
      expect(result.current.pendingConfirmation).not.toBeNull()
    );
    expect(result.current.pendingConfirmation).toMatchObject({
      threadId: 'thread-A',
      // Must equal the DISPLAYED thread or confirmationBelongsToThread rejects
      // the card and Approve refuses to act.
      workspaceThreadId: 'thread-A',
      confirmation: CONFIRMATION,
    });
    expect(resumeStreamMock).toHaveBeenCalledTimes(1);
  });

  it('leaves the gate closed when the server has nothing parked (204)', async () => {
    const { result } = await renderStreaming();

    await waitFor(() => expect(resumeStreamMock).toHaveBeenCalledTimes(1));
    expect(result.current.pendingConfirmation).toBeNull();
  });

  it('probes at most once per thread activation', async () => {
    parkedInterrupt();
    const { result, rerender } = await renderStreaming();

    await waitFor(() =>
      expect(result.current.pendingConfirmation).not.toBeNull()
    );
    rerender();
    rerender();

    expect(resumeStreamMock).toHaveBeenCalledTimes(1);
  });

  it('does not probe a thread this session already owns (run record present)', async () => {
    parkedInterrupt();
    useAgentActivityStore
      .getState()
      .startRun('thread-A', 'NOUS', 'already mine');
    useAgentActivityStore.getState().finishRun('thread-A', 'stopped');

    const { result } = await renderStreaming();
    await new Promise((resolve) => setTimeout(resolve, 30));

    expect(resumeStreamMock).not.toHaveBeenCalled();
    expect(result.current.pendingConfirmation).toBeNull();
  });

  it('does not probe while a stream is live', async () => {
    parkedInterrupt();
    useChatStore.setState({ isStreaming: true });

    await renderStreaming();
    await new Promise((resolve) => setTimeout(resolve, 30));

    expect(resumeStreamMock).not.toHaveBeenCalled();
  });

  it('survives a failing probe without breaking the thread view', async () => {
    resumeStreamMock.mockRejectedValue(new Error('offline'));
    const { result } = await renderStreaming();

    await waitFor(() => expect(resumeStreamMock).toHaveBeenCalled());
    expect(result.current.pendingConfirmation).toBeNull();
  });
});
