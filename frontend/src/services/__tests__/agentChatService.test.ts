/**
 * Unit tests for agentChatService SSE parsing.
 *
 * Focus: chunk-boundary robustness — an SSE frame split across two
 * reader.read() calls must still parse as one event.
 */

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock('@/lib/supabase/client', () => ({
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
  return jest.fn(async () => ({
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
    const done = jest.fn();
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
    const onToolEnd = jest.fn();
    await agentChatService.streamMessage(request, { onToolEnd });
    expect(onToolEnd).toHaveBeenCalledWith('search', 'err', true);
  });

  it('defaults is_error to false when backend omits it', async () => {
    global.fetch = fetchWith([
      'event: tool_end\ndata: {"tool":"search","result":"ok"}\n\n',
    ]);
    const onToolEnd = jest.fn();
    await agentChatService.streamMessage(request, { onToolEnd });
    expect(onToolEnd).toHaveBeenCalledWith('search', 'ok', false);
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
});
