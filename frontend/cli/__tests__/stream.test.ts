/**
 * @jest-environment node
 */
import { streamAgent, streamConfirm } from '../stream';
import * as store from '../auth/store';
import * as client from '../services/client';

jest.mock('../auth/store');
jest.mock('../services/client');

const mockedLoadConfig = store.loadConfig as jest.MockedFunction<
  typeof store.loadConfig
>;
const mockedSaveConfig = store.saveConfig as jest.MockedFunction<
  typeof store.saveConfig
>;
const mockedGetHeaders = client.getCliAuthHeaders as jest.MockedFunction<
  typeof client.getCliAuthHeaders
>;

const CONFIG = {
  token: 'tok_test',
  user_email: 'a@b.com',
  organization_id: 'org_1',
  expires_at: '2099-01-01T00:00:00Z',
  thread_id: null,
};

const HEADERS = {
  'Content-Type': 'application/json',
  Authorization: 'Bearer tok_test',
  'X-Organization-ID': 'org_1',
};

function sseResponse(events: Array<{ event: string; data: unknown }>) {
  const text = events
    .map(
      ({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
    )
    .join('');
  const encoder = new TextEncoder();
  const bytes = encoder.encode(text);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  return { ok: true, status: 200, body: stream };
}

beforeEach(() => {
  mockedLoadConfig.mockReturnValue(CONFIG);
  mockedGetHeaders.mockReturnValue(HEADERS);
});

afterEach(() => jest.clearAllMocks());

test('yields token events', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'token', data: { content: 'Hello ' } },
      { event: 'token', data: { content: 'world' } },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toEqual([
    { type: 'token', content: 'Hello ' },
    { type: 'token', content: 'world' },
    { type: 'done' },
  ]);
});

test('yields tool_start and tool_end events', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'tool_start', data: { tool: 'search_arxiv' } },
      { event: 'tool_end', data: { tool: 'search_arxiv', is_error: false } },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent(
    'search',
    {},
    { fetchFn: mockFetch as any }
  )) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'tool_start',
    tool: 'search_arxiv',
    args: '',
  });
  expect(events).toContainEqual({
    type: 'tool_end',
    tool: 'search_arxiv',
    isError: false,
  });
});

test('yields error event when tool_end has is_error=true', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'tool_start', data: { tool: 'ingest_papers' } },
      { event: 'tool_end', data: { tool: 'ingest_papers', is_error: true } },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent(
    'ingest',
    {},
    { fetchFn: mockFetch as any }
  )) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'tool_end',
    tool: 'ingest_papers',
    isError: true,
  });
});

test('yields confirmation event', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      {
        event: 'confirmation',
        data: { thread_id: 'thread_1', confirmation: { action: 'ingest' } },
      },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('go', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'confirmation',
    threadId: 'thread_1',
    details: { action: 'ingest' },
  });
});

test('yields error event on non-ok response', async () => {
  const mockFetch = jest
    .fn()
    .mockResolvedValue({ ok: false, status: 401, body: null });

  const events: unknown[] = [];
  for await (const e of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toEqual([{ type: 'error', message: 'Stream failed: 401' }]);
});

test('throws when not logged in', async () => {
  mockedLoadConfig.mockReturnValue(null);

  await expect(async () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of streamAgent('hi')) {
    }
  }).rejects.toThrow('Not logged in');
});

test('skips token events with empty content', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'token', data: { content: '' } },
      { event: 'token', data: { content: 'real' } },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(
    events.filter((e) => (e as { type: string }).type === 'token')
  ).toEqual([{ type: 'token', content: 'real' }]);
});

test('persists thread_id from trace event on first turn', async () => {
  mockedLoadConfig.mockReturnValue({ ...CONFIG, thread_id: null });

  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'trace', data: { thread_id: 'abc-123' } },
      { event: 'token', data: { content: 'hi' } },
      { event: 'done', data: {} },
    ])
  );

  for await (const _ of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    // drain
  }

  expect(mockedSaveConfig).toHaveBeenCalledWith(
    expect.objectContaining({ thread_id: 'abc-123' })
  );
});

test('updates thread_id when backend returns a different one', async () => {
  mockedLoadConfig.mockReturnValue({ ...CONFIG, thread_id: 'stale-id' });

  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'trace', data: { thread_id: 'fresh-id' } },
      { event: 'done', data: {} },
    ])
  );

  for await (const _ of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    // drain
  }

  expect(mockedSaveConfig).toHaveBeenCalledWith(
    expect.objectContaining({ thread_id: 'fresh-id' })
  );
});

test('skips save when trace thread_id matches cached thread_id', async () => {
  mockedLoadConfig.mockReturnValue({ ...CONFIG, thread_id: 'same-id' });

  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'trace', data: { thread_id: 'same-id' } },
      { event: 'done', data: {} },
    ])
  );

  for await (const _ of streamAgent('hi', {}, { fetchFn: mockFetch as any })) {
    // drain
  }

  expect(mockedSaveConfig).not.toHaveBeenCalled();
});

test('yields plan event with steps and reasoning', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      {
        event: 'plan',
        data: { steps: ['search arxiv', 'ingest paper'], reasoning: 'why' },
      },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('go', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'plan',
    steps: ['search arxiv', 'ingest paper'],
    reasoning: 'why',
  });
});

test('yields reflection event with passed/issues/round', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      {
        event: 'reflection',
        data: { passed: false, issues: ['missing citations'], round: 2 },
      },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('go', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'reflection',
    passed: false,
    issues: ['missing citations'],
    round: 2,
  });
});

test('yields rag_context event with contexts array', async () => {
  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      {
        event: 'rag_context',
        data: { contexts: [{ id: 'doc1', score: 0.9 }] },
      },
      { event: 'done', data: {} },
    ])
  );

  const events: unknown[] = [];
  for await (const e of streamAgent('go', {}, { fetchFn: mockFetch as any })) {
    events.push(e);
  }

  expect(events).toContainEqual({
    type: 'rag_context',
    contexts: [{ id: 'doc1', score: 0.9 }],
  });
});

test('streamConfirm persists thread_id rotation from trace event', async () => {
  mockedLoadConfig.mockReturnValue({ ...CONFIG, thread_id: 'stale-id' });

  const mockFetch = jest.fn().mockResolvedValue(
    sseResponse([
      { event: 'trace', data: { thread_id: 'rotated-id' } },
      { event: 'done', data: {} },
    ])
  );

  for await (const _ of streamConfirm('stale-id', true, {
    fetchFn: mockFetch as any,
  })) {
    // drain
  }

  expect(mockedSaveConfig).toHaveBeenCalledWith(
    expect.objectContaining({ thread_id: 'rotated-id' })
  );
});

test('emits IDLE_TIMEOUT sentinel error when no events arrive within idleTimeoutMs', async () => {
  const slowResponse = {
    ok: true,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        // never enqueue anything; stream hangs
        void controller;
      },
    }),
  };
  const mockFetch = jest.fn().mockResolvedValue(slowResponse);

  const events: unknown[] = [];
  for await (const e of streamAgent(
    'hi',
    {},
    { fetchFn: mockFetch as never, idleTimeoutMs: 50 }
  )) {
    events.push(e);
    if ((e as { type: string }).type === 'error') break;
  }

  expect(events).toContainEqual({
    type: 'error',
    message: expect.stringMatching(/^IDLE_TIMEOUT:0$/),
  });
});
