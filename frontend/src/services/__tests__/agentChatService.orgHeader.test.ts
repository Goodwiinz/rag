/**
 * Regression test for audit C9: the agent SSE stream sender must NOT emit the
 * dead `X-Organization-ID` header. The backend derives the tenant from the
 * authenticated user (`current_user`); the header was never read inbound and
 * its CORS allowlist entry has been removed. Even when the Supabase session
 * carries an `organization_id` in its user metadata, no such header may be sent
 * (sending it would trip a CORS preflight rejection now that the allowlist
 * entry is gone).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

// Session WITH an organization_id in user metadata — the value the removed
// sender used to copy into the X-Organization-ID header.
vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: {
          session: {
            access_token: 'session-token',
            user: { user_metadata: { organization_id: 'org-123' } },
          },
        },
      }),
    },
  }),
}));

import { agentChatService } from '../agentChatService';

function makeReader(chunks: string[]) {
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

const request = {
  messages: [{ role: 'user', content: 'hi' }],
  page_context: { type: 'chat' },
};

describe('agentChatService stream auth headers', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
    vi.clearAllMocks();
  });

  it('sends Authorization but never X-Organization-ID on streamMessage', async () => {
    global.fetch = fetchWith(['event: done\ndata: {"status":"complete"}\n\n']);
    await agentChatService.streamMessage(request, { onDone: vi.fn() });

    const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer session-token');
    expect(headers).not.toHaveProperty('X-Organization-ID');
  });

  it('sends Authorization but never X-Organization-ID on resumeStream', async () => {
    global.fetch = fetchWith(['event: done\ndata: {"status":"complete"}\n\n']);
    await agentChatService.resumeStream('thread-1', 0, { onDone: vi.fn() });

    const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
    // resumeStream builds a Headers instance (it adds Last-Event-ID on top of
    // the auth headers), so read through the Headers API rather than assuming
    // a plain record.
    const headers = new Headers(init.headers);
    expect(headers.get('Authorization')).toBe('Bearer session-token');
    expect(headers.get('X-Organization-ID')).toBeNull();
    expect(headers.get('Last-Event-ID')).toBe('0');
  });
});
