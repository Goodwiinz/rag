import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
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
  return {
    messages: [] as ChatPageMessage[],
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

describe('useChatStreaming AUI_FULL in-band HITL approval', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamConfirmMock.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('opens the bridge + an approval message, and approve routes to streamConfirm', async () => {
    vi.stubEnv('NEXT_PUBLIC_AUI_FULL', 'true');
    vi.resetModules();
    // Import the bridge from the SAME reset module graph the hook uses, else
    // they resolve to different store instances.
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const { useHitlBridge } = await import(
      '@/components/chat/aui/hitlBridge'
    );

    let current: ChatPageMessage[] = [];
    const setMessages = vi.fn((m: unknown) => {
      current = typeof m === 'function'
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

    // The gate is mirrored into the bridge with the confirmed tool preview.
    const bridge = useHitlBridge.getState();
    expect(bridge.request).toMatchObject({
      toolName: 'ingest_arxiv_papers',
      args: { paper_ids: ['2605.1'] },
    });
    expect(bridge.respond).toBeTypeOf('function');

    // ...and surfaced as an in-band approval message in the transcript.
    const approvalMsg = current.find((m) => m.pendingApproval);
    expect(approvalMsg?.pendingApproval?.toolName).toBe('ingest_arxiv_papers');

    // Approve routes through the bridge to the hardened confirm flow.
    await act(async () => {
      bridge.respond?.(true);
    });
    expect(streamConfirmMock).toHaveBeenCalledTimes(1);
    expect(streamConfirmMock.mock.calls[0][0]).toMatchObject({
      confirmed: true,
    });
  });
});
