/**
 * Resume-on-mount: a stale `running` run in the agent activity store for the
 * displayed thread must trigger agentChatService.resumeStream (from the last
 * seen seq), and a 204/{resumed:false} must clear the stale run record.
 */

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

// ---- Mocks ----
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
    createMessage: vi.fn().mockResolvedValue({ id: 'db-msg-1' }),
    listMessages: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { useChatStore } from '@/store/chat-store';

function makeParams() {
  const activeConversationIdRef = { current: 'thread-A' as string | null };
  return {
    messages: [
      { role: 'user', content: 'earlier question', timestamp: 1 },
    ] as ChatPageMessage[],
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    activeConversationId: 'thread-A',
    setActiveConversationId: vi.fn(),
    activeConversationIdRef,
    dbConversation: null,
    isAuthenticated: true,
    setCurrentThread: vi.fn(),
    addMessageToStore: vi.fn(),
    enableRAG: false,
  };
}

describe('useChatStreaming stream resume on mount', () => {
  beforeEach(() => {
    resumeStreamMock.mockReset();
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
    useChatStore.setState({ isStreaming: false });
  });

  it('resumes a stale running run from its streamSeq when not streaming', async () => {
    useAgentActivityStore.getState().startRun('thread-A', 'Agent', 'task');
    useAgentActivityStore.getState().setStreamSeq('thread-A', 7);
    resumeStreamMock.mockResolvedValue({ resumed: true });

    await act(async () => {
      renderHook(() => useChatStreaming(makeParams()), { wrapper });
    });

    expect(resumeStreamMock).toHaveBeenCalledTimes(1);
    expect(resumeStreamMock.mock.calls[0][0]).toBe('thread-A');
    expect(resumeStreamMock.mock.calls[0][1]).toBe(7);
  });

  it('clears the stale run on {resumed:false} and does not resume twice', async () => {
    useAgentActivityStore.getState().startRun('thread-A', 'Agent', 'task');
    resumeStreamMock.mockResolvedValue({ resumed: false });

    let rerender: () => void = () => {};
    await act(async () => {
      ({ rerender } = renderHook(() => useChatStreaming(makeParams()), {
        wrapper,
      }));
    });
    await act(async () => {
      rerender();
    });

    expect(resumeStreamMock).toHaveBeenCalledTimes(1);
    // defaults streamSeq to 0 when never set
    expect(resumeStreamMock.mock.calls[0][1]).toBe(0);
    expect(useAgentActivityStore.getState().runs['thread-A'].state).toBe(
      'done'
    );
  });

  it('does not resume when there is no run for the thread', async () => {
    await act(async () => {
      renderHook(() => useChatStreaming(makeParams()), { wrapper });
    });
    expect(resumeStreamMock).not.toHaveBeenCalled();
  });
});
