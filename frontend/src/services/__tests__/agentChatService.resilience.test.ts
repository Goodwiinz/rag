/**
 * Round-3 audit regressions in the stream transport: H7 (no dead-stream
 * watchdog), M4 (a trimmed replay is accepted silently) and M15 (a 401 on
 * stream open is reported as the user's fault with no retry).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/apiClient', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const refreshSession = vi.hoisted(() => vi.fn(async () => ({ data: {} })));
const getSession = vi.hoisted(() =>
  vi.fn(async () => ({ data: { session: { access_token: 'token-1' } } }))
);
vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({ auth: { getSession, refreshSession } }),
}));

import {
  agentChatService,
  STREAM_SILENCE_TIMEOUT_MS,
  StreamStalledError,
} from '../agentChatService';

const request = {
  messages: [{ role: 'user', content: 'hi' }],
  page_context: { type: 'chat' },
};

function readerFrom(chunks: string[]): {
  getReader: () => {
    read: () => Promise<ReadableStreamReadResult<Uint8Array>>;
    cancel: () => Promise<void>;
    releaseLock: () => void;
  };
} {
  const encoder = new TextEncoder();
  const queue = chunks.map((c) => encoder.encode(c));
  let i = 0;
  return {
    getReader: () => ({
      async read() {
        if (i >= queue.length) return { done: true, value: undefined };
        return { done: false, value: queue[i++] };
      },
      async cancel() {},
      releaseLock() {},
    }),
  };
}

/** A body whose first read never settles — a silently dead connection. */
function silentReader(): {
  getReader: () => {
    read: () => Promise<ReadableStreamReadResult<Uint8Array>>;
    cancel: () => Promise<void>;
    releaseLock: () => void;
  };
} {
  return {
    getReader: () => ({
      read: () => new Promise<never>(() => {}),
      async cancel() {},
      releaseLock() {},
    }),
  };
}

const realFetch = global.fetch;

describe('agentChatService stream resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue({
      data: { session: { access_token: 'token-1' } },
    });
  });
  afterEach(() => {
    global.fetch = realFetch;
    vi.useRealTimers();
  });

  it('gives up on a stream that goes silent (H7)', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: silentReader(),
    })) as unknown as typeof fetch;

    const pending = agentChatService.streamMessage(request, {});
    const assertion =
      expect(pending).rejects.toBeInstanceOf(StreamStalledError);
    await vi.advanceTimersByTimeAsync(STREAM_SILENCE_TIMEOUT_MS + 1_000);
    await assertion;
  });

  it('reports a trimmed replay as a gap instead of accepting it (M4)', async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: readerFrom([
        'id: 4200\nevent: token\ndata: {"content":"tail"}\n\n',
        'event: done\ndata: {"status":"complete"}\n\n',
      ]),
    })) as unknown as typeof fetch;

    const onReplayGap = vi.fn();
    const result = await agentChatService.resumeStream(
      'thread-A',
      12,
      { onReplayGap },
      undefined
    );

    expect(result.status).toBe('resumed');
    expect(onReplayGap).toHaveBeenCalledWith(4200, 13);
  });

  it('does not report a gap when the replay is contiguous', async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      body: readerFrom([
        'id: 13\nevent: token\ndata: {"content":"next"}\n\n',
        'event: done\ndata: {"status":"complete"}\n\n',
      ]),
    })) as unknown as typeof fetch;

    const onReplayGap = vi.fn();
    await agentChatService.resumeStream('thread-A', 12, { onReplayGap });

    expect(onReplayGap).not.toHaveBeenCalled();
  });

  it('retries a 401 once with a refreshed session (M15)', async () => {
    let call = 0;
    global.fetch = vi.fn(async () => {
      call += 1;
      if (call === 1) {
        return {
          ok: false,
          status: 401,
          body: null,
          json: async () => ({}),
          text: async () => '',
        };
      }
      return {
        ok: true,
        status: 200,
        body: readerFrom(['event: done\ndata: {"status":"complete"}\n\n']),
      };
    }) as unknown as typeof fetch;

    const onDone = vi.fn();
    const onError = vi.fn();
    await agentChatService.streamMessage(request, { onDone, onError });

    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('does not blame the user when the retried 401 still fails', async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 401,
      body: null,
      json: async () => ({}),
      text: async () => '',
    })) as unknown as typeof fetch;

    const onError = vi.fn();
    await agentChatService.streamMessage(request, { onError });

    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);
    // Category stays undefined: an expired session is not an invalid request.
    expect(onError.mock.calls[0][1]).toBeUndefined();
  });
});
