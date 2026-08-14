// Durable edit-and-resend: the wire contract.
//
// PR #1313's edit only truncated the REQUEST — the server kept the old answer
// and every later turn, so a reload contradicted what the user saw and the
// model could still see the replaced prompt. The turn now names the message it
// supersedes, and the server tombstones it.
//
// Two properties this pins down:
//  1. An edit sends `supersedes_client_message_id` = the edited turn's
//     persisted cmid, AND a FRESH `client_message_id` on the new user turn —
//     reusing the old id would hit the server's ON CONFLICT dedup and be
//     silently dropped.
//  2. A normal send omits the field entirely (not null, not empty string).
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactElement, type ReactNode } from 'react';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { makeChatPageMessage } from '@/test/chatMessageFactory';
import { useChatStore } from '@/store/chat-store';

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

const EDITED_CMID = '11111111-1111-4111-8111-111111111111';

const history: ChatPageMessage[] = [
  makeChatPageMessage({
    id: 'first-user',
    role: 'user',
    content: 'first turn',
    timestamp: 1,
    clientMessageId: EDITED_CMID,
  }),
  makeChatPageMessage({
    id: 'first-assistant',
    role: 'assistant',
    content: 'first reply',
    timestamp: 2,
  }),
];

function makeParams(
  overrides: Record<string, unknown> = {}
): Record<string, unknown> {
  useChatStore.setState({ currentThreadId: 'thread-A' });
  return {
    messages: [] as ChatPageMessage[],
    displayedMessages: history,
    setMessages: vi.fn(),
    conversations: [],
    setConversations: vi.fn(),
    dbConversation: null,
    enableRAG: false,
    ...overrides,
  };
}

type Payload = {
  messages: Array<{ role: string; content: string; client_message_id?: string }>;
  supersedes_client_message_id?: string;
};

describe('useChatStreaming edit-and-resend', () => {
  beforeEach(() => {
    streamMessageMock.mockReset();
    streamMessageMock.mockImplementation(
      (_req: unknown, cb: { onDone?: (p?: unknown) => void }) => {
        cb.onDone?.({});
        return Promise.resolve();
      }
    );
  });

  it('sends the superseded cmid plus a FRESH id on the new turn', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await act(async () => {
      // Edit the first turn: history truncated to before it, and that turn's
      // persisted cmid named as superseded.
      await result.current.handleSubmit('first turn, edited', [], EDITED_CMID);
    });

    const payload = streamMessageMock.mock.calls[0][0] as Payload;
    expect(payload.supersedes_client_message_id).toBe(EDITED_CMID);

    const lastTurn = payload.messages[payload.messages.length - 1];
    expect(lastTurn.role).toBe('user');
    expect(lastTurn.content).toBe('first turn, edited');
    expect(lastTurn.client_message_id).toBeTruthy();
    // FRESH — a reused id would be swallowed by the server's ON CONFLICT dedup.
    expect(lastTurn.client_message_id).not.toBe(EDITED_CMID);
  });

  it('omits the field entirely on a normal send', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('follow-up');
    });

    const payload = streamMessageMock.mock.calls[0][0] as Payload;
    expect('supersedes_client_message_id' in payload).toBe(false);
  });

  it('omits the field when the edited turn was never persisted with a cmid', async () => {
    const { useChatStreaming } = await import('@/hooks/chat/useChatStreaming');
    const { result } = renderHook(() => useChatStreaming(makeParams()), {
      wrapper,
    });

    await act(async () => {
      await result.current.handleSubmit('edited', [], undefined);
    });

    const payload = streamMessageMock.mock.calls[0][0] as Payload;
    expect('supersedes_client_message_id' in payload).toBe(false);
  });
});
