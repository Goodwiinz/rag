/**
 * Unit tests for agentChatService SSE parsing.
 *
 * Focus: chunk-boundary robustness — an SSE frame split across two
 * reader.read() calls must still parse as one event.
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
      getSession: async () => ({ data: { session: null } }),
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

describe('agentChatService.streamMessage SSE parsing', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it('parses frames that arrive in a single chunk', async () => {
    global.fetch = fetchWith([
      'event: token\ndata: {"content":"hello"}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ]);
    const tokens: string[] = [];
    const done = vi.fn();
    await agentChatService.streamMessage(request, {
      onToken: (c) => tokens.push(c),
      onDone: done,
    });
    expect(tokens).toEqual(['hello']);
    expect(done).toHaveBeenCalledTimes(1);
  });

  it('parses a frame split between event: and data: lines across chunks', async () => {
    // The event line arrives in chunk 1; the data line arrives in chunk 2.
    // Before Fix 1, eventType would reset to '' between chunks and the event
    // would be dropped silently.
    global.fetch = fetchWith([
      'event: token\n',
      'data: {"content":"split"}\n\n',
    ]);
    const tokens: string[] = [];
    await agentChatService.streamMessage(request, {
      onToken: (c) => tokens.push(c),
    });
    expect(tokens).toEqual(['split']);
  });

  it('tolerates CRLF line endings from intermediate proxies', async () => {
    global.fetch = fetchWith([
      'event: token\r\ndata: {"content":"crlf"}\r\n\r\n',
    ]);
    const tokens: string[] = [];
    await agentChatService.streamMessage(request, {
      onToken: (c) => tokens.push(c),
    });
    expect(tokens).toEqual(['crlf']);
  });

  it('forwards is_error flag to onToolEnd', async () => {
    global.fetch = fetchWith([
      'event: tool_end\ndata: {"tool":"search","result":"err","is_error":true}\n\n',
    ]);
    const onToolEnd = vi.fn();
    await agentChatService.streamMessage(request, { onToolEnd });
    expect(onToolEnd).toHaveBeenCalledWith('search', 'err', true);
  });

  it('defaults is_error to false when backend omits it', async () => {
    global.fetch = fetchWith([
      'event: tool_end\ndata: {"tool":"search","result":"ok"}\n\n',
    ]);
    const onToolEnd = vi.fn();
    await agentChatService.streamMessage(request, { onToolEnd });
    expect(onToolEnd).toHaveBeenCalledWith('search', 'ok', false);
  });

  it('forwards per-turn token usage to onUsage', async () => {
    global.fetch = fetchWith([
      'event: usage\ndata: {"input_tokens":1234,"output_tokens":340}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ]);
    const onUsage = vi.fn();
    await agentChatService.streamMessage(request, { onUsage });
    expect(onUsage).toHaveBeenCalledWith(1234, 340);
  });

  it('forwards heartbeat elapsed_ms as live progress', async () => {
    // The keepalive is the ONLY signal during a silent planner/LLM phase —
    // dropping it (as the consumer used to) leaves a 60s run with no progress.
    global.fetch = fetchWith([
      'event: heartbeat\ndata: {"elapsed_ms":47000}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ]);
    const onHeartbeat = vi.fn();
    await agentChatService.streamMessage(request, { onHeartbeat });
    expect(onHeartbeat).toHaveBeenCalledWith(47000);
  });

  it('defaults a heartbeat with no elapsed_ms to zero', async () => {
    global.fetch = fetchWith(['event: heartbeat\ndata: {}\n\n']);
    const onHeartbeat = vi.fn();
    await agentChatService.streamMessage(request, { onHeartbeat });
    expect(onHeartbeat).toHaveBeenCalledWith(0);
  });

  it('defaults missing token counts to zero on the usage event', async () => {
    global.fetch = fetchWith(['event: usage\ndata: {}\n\n']);
    const onUsage = vi.fn();
    await agentChatService.streamMessage(request, { onUsage });
    expect(onUsage).toHaveBeenCalledWith(0, 0);
  });

  it('skips malformed JSON data lines without aborting the stream', async () => {
    global.fetch = fetchWith([
      'event: token\ndata: {not json}\n\n',
      'event: token\ndata: {"content":"after"}\n\n',
    ]);
    const tokens: string[] = [];
    await agentChatService.streamMessage(request, {
      onToken: (c) => tokens.push(c),
    });
    expect(tokens).toEqual(['after']);
  });

  it('flushes a trailing frame that ended without a final newline', async () => {
    // The server's last chunk ends mid-frame (no trailing \n). Without
    // the defensive buffer flush, the final done event is silently dropped.
    global.fetch = fetchWith([
      'event: token\ndata: {"content":"hello"}\n\n',
      'event: done\ndata: {"status":"complete"}',
    ]);
    const tokens: string[] = [];
    const done = vi.fn();
    await agentChatService.streamMessage(request, {
      onToken: (c) => tokens.push(c),
      onDone: done,
    });
    expect(tokens).toEqual(['hello']);
    expect(done).toHaveBeenCalledTimes(1);
  });
});

describe('agentChatService.resumeStream', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it('treats 204 as a clean no-op: no callbacks, {resumed:false}', async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 204,
      body: null,
    })) as unknown as typeof fetch;
    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    const res = await agentChatService.resumeStream('thread-1', 0, {
      onToken,
      onDone,
      onError,
    });
    expect(res).toEqual({ resumed: false });
    expect(onToken).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('replays buffered frames and reports increasing seqs via onSeq', async () => {
    global.fetch = fetchWith([
      'id: 3\nevent: token\ndata: {"content":"he"}\n\n',
      'id: 4\nevent: token\ndata: {"content":"llo"}\n\n',
      'id: 5\nevent: done\ndata: {"status":"complete"}\n\n',
    ]);
    const tokens: string[] = [];
    const seqs: number[] = [];
    const onDone = vi.fn();
    const res = await agentChatService.resumeStream('thread-1', 2, {
      onToken: (c) => tokens.push(c),
      onSeq: (s) => seqs.push(s),
      onDone,
    });
    expect(res).toEqual({ resumed: true });
    expect(tokens).toEqual(['he', 'llo']);
    expect(seqs).toEqual([3, 4, 5]);
    expect(onDone).toHaveBeenCalledTimes(1);
    // GET with the after cursor in the query string
    const url = vi.mocked(global.fetch).mock.calls[0][0] as string;
    expect(url).toContain('/agent/stream/resume/thread-1?after=2');
  });

  it('reports seqs on the live streamMessage path too', async () => {
    global.fetch = fetchWith([
      'id: 1\nevent: token\ndata: {"content":"x"}\n\n',
      'id: 2\nevent: done\ndata: {"status":"complete"}\n\n',
    ]);
    const seqs: number[] = [];
    await agentChatService.streamMessage(request, {
      onSeq: (s) => seqs.push(s),
    });
    expect(seqs).toEqual([1, 2]);
  });
});

describe('agentChatService.streamConfirm SSE parsing', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  const confirmRequest = { thread_id: 'thread-1', confirmed: true };

  it('forwards per-turn token usage to onUsage on the confirm path', async () => {
    global.fetch = fetchWith([
      'event: usage\ndata: {"input_tokens":1234,"output_tokens":340}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ]);
    const onUsage = vi.fn();
    await agentChatService.streamConfirm(confirmRequest, { onUsage });
    expect(onUsage).toHaveBeenCalledWith(1234, 340);
  });

  it('defaults missing token counts to zero on the confirm usage event', async () => {
    global.fetch = fetchWith(['event: usage\ndata: {}\n\n']);
    const onUsage = vi.fn();
    await agentChatService.streamConfirm(confirmRequest, { onUsage });
    expect(onUsage).toHaveBeenCalledWith(0, 0);
  });
});
