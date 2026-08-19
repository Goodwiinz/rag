/**
 * streamMessage must cap the outgoing messages array at the backend's
 * AgentExecuteRequest max_length (50), keeping the newest tail. Callers send
 * the full displayed history plus the new turn, so a 50-message thread's next
 * send was 51 messages -> 422 -> the non-retriable "This request can't be
 * retried as-is." error bubble.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: 'session-token', user: {} } },
      }),
    },
  }),
}));

import { agentChatService } from '../agentChatService';

function makeReader(chunks: string[]): {
  read(): Promise<{ done: boolean; value: Uint8Array | undefined }>;
  releaseLock(): void;
} {
  const encoder = new TextEncoder();
  const queue = chunks.map((c) => encoder.encode(c));
  let i = 0;
  return {
    async read() {
      if (i >= queue.length) return { done: true, value: undefined };
      return { done: false, value: queue[i++] };
    },
    releaseLock() {},
  };
}

function fetchWith(chunks: string[]): typeof fetch {
  return vi.fn(async () => ({
    ok: true,
    status: 200,
    body: { getReader: () => makeReader(chunks) },
  })) as unknown as typeof fetch;
}

describe('agentChatService streamMessage message cap', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
    vi.clearAllMocks();
  });

  it('caps a 51-message history to the newest 50', async () => {
    global.fetch = fetchWith(['event: done\ndata: {"status":"complete"}\n\n']);
    const messages = Array.from({ length: 51 }, (_, i) => ({
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `turn-${i}`,
    }));
    await agentChatService.streamMessage(
      { messages, page_context: { type: 'chat' } },
      { onDone: vi.fn() }
    );

    const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
    const sent = JSON.parse(init.body as string);
    expect(sent.messages).toHaveLength(50);
    // Newest tail: the first (oldest) turn is dropped, the new turn survives.
    expect(sent.messages[0].content).toBe('turn-1');
    expect(sent.messages[49].content).toBe('turn-50');
  });

  it('leaves a small history untouched', async () => {
    global.fetch = fetchWith(['event: done\ndata: {"status":"complete"}\n\n']);
    await agentChatService.streamMessage(
      {
        messages: [{ role: 'user', content: 'hi' }],
        page_context: { type: 'chat' },
      },
      { onDone: vi.fn() }
    );

    const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
    const sent = JSON.parse(init.body as string);
    expect(sent.messages).toHaveLength(1);
  });
});
