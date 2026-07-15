import { describe, expect, it } from 'vitest';
import {
  isThreadSwitchPending,
  mapDbMessageToChatPageMessage,
  mapStoreMessagesToChatMessages,
  selectDisplayedMessages,
  summarizeToolArgs,
  summarizeToolResult,
  syncConversationMessagesWithStore,
} from '../cloudMessageView';

describe('cloudMessageView', () => {
  it('maps persisted store messages into chat page message shape', () => {
    const result = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        client_message_id: 'runtime-m-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [{ document_title: 'Doc 1', score: 0.8 }],
      } as any,
    ]);

    expect(result[0].role).toBe('assistant');
    expect(result[0].content).toBe('Answer');
    expect(result[0].citations?.[0].title).toBe('Doc 1');
    expect(result[0].runtimeId).toBe('runtime-m-1');
    expect(result[0].source).toBe('canonical');
  });

  it('falls back to the persisted id for legacy rows without a client id', () => {
    const message = mapDbMessageToChatPageMessage({
      id: 'legacy-message-id',
      client_message_id: null,
      role: 'user',
      content: 'Legacy question',
      created_at: '2026-03-09T12:00:00Z',
      citations: [],
    } as any);

    expect(message.runtimeId).toBe('legacy-message-id');
    expect(message.source).toBe('canonical');
  });

  it('carries the stopped flag and latency from a persisted message into metadata', () => {
    const [withStop, plain] = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        role: 'assistant',
        content: 'Partial',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
        latency_ms: 1500,
        stopped: true,
      } as any,
      {
        id: 'm-2',
        role: 'assistant',
        content: 'Complete',
        created_at: '2026-03-09T12:00:01Z',
        citations: [],
      } as any,
    ]);

    expect(withStop.metadata?.stopped).toBe(true);
    expect(withStop.metadata?.responseTimeMs).toBe(1500);
    expect(plain.metadata).toBeUndefined();
  });

  it('maps persisted plan and token usage into the chat page message', () => {
    const [msg] = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
        plan: [
          {
            step: 1,
            description: 'Search documents',
            tool: 'search_documents',
            args_hint: { query: 'transformers' },
            depends_on: [],
          },
        ],
        token_usage: { input_tokens: 1200, output_tokens: 340 },
      } as any,
    ]);

    expect(msg.plan).toHaveLength(1);
    expect(msg.plan?.[0].tool).toBe('search_documents');
    expect(msg.metadata?.tokenUsage).toEqual({ input: 1200, output: 340 });
  });

  it('leaves plan and tokenUsage absent for rows persisted without them', () => {
    const [msg] = mapStoreMessagesToChatMessages([
      {
        id: 'm-2',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
      } as any,
    ]);

    expect(msg.plan).toBeUndefined();
    expect(msg.metadata).toBeUndefined();
  });

  // Regression: the lazy-load path (`useChatSession.mapDbMessageToUiMessage`)
  // previously had a second mapper copy that silently dropped plan +
  // token_usage on thread switch / warm start. It now delegates to
  // mapDbMessageToChatPageMessage, so both paths must agree.
  describe('mapDbMessageToChatPageMessage (canonical single-message mapper)', () => {
    it('carries plan + token_usage so the lazy-load path matches the store path', () => {
      const db = {
        id: 'm-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
        latency_ms: 900,
        plan: [
          {
            step: 1,
            description: 'Search',
            tool: 'search_documents',
            args_hint: {},
            depends_on: [],
          },
        ],
        token_usage: { input_tokens: 42, output_tokens: 7 },
      } as any;

      const fromSingle = mapDbMessageToChatPageMessage(db);
      const [fromArray] = mapStoreMessagesToChatMessages([db]);

      expect(fromSingle.plan).toEqual(fromArray.plan);
      expect(fromSingle.metadata?.tokenUsage).toEqual(
        fromArray.metadata?.tokenUsage
      );
      expect(fromSingle.metadata?.tokenUsage).toEqual({
        input: 42,
        output: 7,
      });
      expect(fromSingle.metadata?.responseTimeMs).toBe(900);
      expect(fromSingle).toEqual(fromArray);
    });

    it('omits plan/metadata when the row carries no provenance', () => {
      const msg = mapDbMessageToChatPageMessage({
        id: 'm-2',
        role: 'user',
        content: 'hi',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
      } as any);

      expect(msg.plan).toBeUndefined();
      expect(msg.metadata).toBeUndefined();
    });
  });

  it('uses store-backed messages for cloud chat once persisted messages are available', () => {
    const localMessages = [
      {
        role: 'user' as const,
        content: 'optimistic',
        timestamp: 1,
      },
    ];

    const displayed = selectDisplayedMessages({
      localMessages,
      storeMessages: [
        {
          id: 'm-1',
          role: 'user',
          content: 'persisted user',
          created_at: '2026-03-09T12:00:00Z',
          citations: [],
        } as any,
        {
          id: 'm-2',
          role: 'assistant',
          content: 'persisted assistant',
          created_at: '2026-03-09T12:00:01Z',
          citations: [],
        } as any,
      ],
    });

    expect(displayed.map((message) => message.content)).toEqual([
      'persisted user',
      'persisted assistant',
    ]);
  });

  it('keeps local messages for cloud chat until store-backed messages exist', () => {
    const localMessages = [
      {
        role: 'user' as const,
        content: 'optimistic',
        timestamp: 1,
      },
    ];

    expect(
      selectDisplayedMessages({
        localMessages,
        storeMessages: [],
      })
    ).toEqual(localMessages);
  });

  it('keeps local optimistic messages displayed even while a store page is in flight', () => {
    // Regression guard for #1121: the selector must never blanket-hide local
    // messages on a global loading flag — the first send in a new chat has a
    // load in flight for the very thread the local turn belongs to. Stale
    // cross-thread paint is prevented upstream (local messages are cleared /
    // re-adopted per thread on switch), not here.
    const localMessages = [
      {
        role: 'user' as const,
        content: 'just sent',
        timestamp: 1,
      },
    ];

    expect(
      selectDisplayedMessages({
        localMessages,
        storeMessages: [],
      })
    ).toEqual(localMessages);
  });

  it('uses store-backed messages when persisted state is ahead of local cache', () => {
    const displayed = selectDisplayedMessages({
      localMessages: [
        {
          id: 'm-1',
          role: 'user' as const,
          content: 'persisted user',
          timestamp: 1,
        },
      ],
      storeMessages: [
        {
          id: 'm-1',
          role: 'user',
          content: 'persisted user',
          created_at: '2026-03-09T12:00:00Z',
          citations: [],
        } as any,
        {
          id: 'm-2',
          role: 'assistant',
          content: 'persisted assistant',
          created_at: '2026-03-09T12:00:01Z',
          citations: [],
        } as any,
      ],
    });

    expect(displayed.map((message) => message.content)).toEqual([
      'persisted user',
      'persisted assistant',
    ]);
  });

  it('syncs persisted cloud messages back into the sidebar conversation cache', () => {
    const conversations = [
      {
        id: 'thread-1',
        title: 'Thread 1',
        messages: [],
        updatedAt: 1,
        messageCount: 2,
      },
      {
        id: 'thread-2',
        title: 'Thread 2',
        messages: [],
        updatedAt: 2,
      },
    ];

    const result = syncConversationMessagesWithStore(
      conversations,
      'thread-1',
      [
        {
          id: 'm-1',
          role: 'user',
          content: 'persisted user',
          created_at: '2026-03-09T12:00:00Z',
          citations: [],
        } as any,
        {
          id: 'm-2',
          role: 'assistant',
          content: 'persisted assistant',
          created_at: '2026-03-09T12:00:01Z',
          citations: [],
        } as any,
      ]
    );

    expect(result[0].messages.map((message) => message.content)).toEqual([
      'persisted user',
      'persisted assistant',
    ]);
    expect(result[1]).toBe(conversations[1]);
    expect(result[0].updatedAt).toBe(
      new Date('2026-03-09T12:00:01Z').getTime()
    );
  });

  it('preserves a larger authoritative thread count when only a message page is loaded', () => {
    const result = syncConversationMessagesWithStore(
      [
        {
          id: 'thread-1',
          title: 'Thread 1',
          messages: [],
          updatedAt: 1,
          messageCount: 120,
        },
      ],
      'thread-1',
      Array.from({ length: 100 }, (_, index) => ({
        id: `m-${index}`,
        role: index % 2 === 0 ? 'user' : 'assistant',
        content: `message ${index}`,
        created_at: `2026-03-09T12:${String(index).padStart(2, '0')}:00Z`,
        citations: [],
      })) as any
    );

    expect(result[0].messageCount).toBe(120);
  });
});

describe('mapDbToolExecutions', () => {
  it('returns undefined for absent or empty executions', async () => {
    const { mapDbToolExecutions } = await import('../cloudMessageView');
    expect(mapDbToolExecutions(undefined)).toBeUndefined();
    expect(mapDbToolExecutions([])).toBeUndefined();
  });

  it('maps persisted rows onto activity steps', async () => {
    const { mapDbToolExecutions } = await import('../cloudMessageView');
    const steps = mapDbToolExecutions([
      {
        id: 'te-1',
        tool_name: 'search_arxiv',
        tool_display_name: 'Search arXiv',
        args: { query: 'rag' },
        status: 'completed',
        duration_ms: 1234,
      },
      { tool_name: 'ingest_document', status: 'failed', error: 'boom' },
      { tool_name: 'bare_tool' },
    ]);
    expect(steps).toEqual([
      {
        tool: 'search_arxiv',
        label: 'Search arXiv',
        status: 'done',
        durationMs: 1234,
        argsSummary: 'query: rag',
        args: { query: 'rag' },
      },
      {
        tool: 'ingest_document',
        label: 'ingest_document',
        status: 'error',
        resultSummary: 'boom',
      },
      { tool: 'bare_tool', label: 'bare_tool', status: 'done' },
    ]);
  });

  it('flows tool_executions through mapStoreMessagesToChatMessages', () => {
    const [msg] = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [],
        tool_executions: [
          { tool_name: 'search_documents', status: 'completed' },
        ],
      } as any,
    ]);
    expect(msg.toolExecutions).toEqual([
      { tool: 'search_documents', label: 'search_documents', status: 'done' },
    ]);
  });
});

describe('summarizeToolArgs', () => {
  it('returns undefined for missing or empty args', () => {
    expect(summarizeToolArgs(undefined)).toBeUndefined();
    expect(summarizeToolArgs({})).toBeUndefined();
  });

  it('joins key/value pairs, skipping null values', () => {
    expect(
      summarizeToolArgs({ query: 'rag', max_results: 5, categories: null })
    ).toBe('query: rag · max_results: 5');
  });

  it('truncates long summaries to one line', () => {
    const long = summarizeToolArgs({ query: 'x'.repeat(300) });
    expect(long!.length).toBeLessThanOrEqual(140);
    expect(long!.endsWith('…')).toBe(true);
  });
});

describe('summarizeToolResult', () => {
  it('returns undefined for empty result', () => {
    expect(summarizeToolResult(undefined)).toBeUndefined();
    expect(summarizeToolResult('')).toBeUndefined();
  });

  it('prefers error over message field in JSON payloads', () => {
    expect(
      summarizeToolResult(JSON.stringify({ message: 'ok', error: 'boom' }))
    ).toBe('boom');
    expect(summarizeToolResult(JSON.stringify({ message: 'found 3' }))).toBe(
      'found 3'
    );
  });

  it('falls back to truncated raw text for non-JSON results', () => {
    expect(summarizeToolResult('plain text')).toBe('plain text');
    const long = summarizeToolResult('y'.repeat(300));
    expect(long!.length).toBeLessThanOrEqual(140);
  });
});

describe('syncConversationMessagesWithStore — post-eviction unfreeze', () => {
  const conv = (messages: any[]) => [
    {
      id: 'thread-1',
      title: 'Thread 1',
      messages,
      updatedAt: 1,
      messageCount: messages.length,
    },
  ];
  const dbMsg = (id: string, iso: string) =>
    ({
      id,
      role: 'assistant',
      content: `m-${id}`,
      created_at: iso,
      citations: [],
    }) as any;

  it('still ignores a shorter, not-newer store page (partial load)', () => {
    const cached = [
      { id: 'a', role: 'user' as const, content: 'a', timestamp: 1000 },
      { id: 'b', role: 'assistant' as const, content: 'b', timestamp: 2000 },
    ];
    const result = syncConversationMessagesWithStore(conv(cached), 'thread-1', [
      dbMsg('a', '1970-01-01T00:00:01Z'),
    ]);
    expect(result[0].messages).toBe(cached);
  });

  it('accepts a shorter store page whose tail is newer (post-eviction reload)', () => {
    const cached = [
      { id: 'a', role: 'user' as const, content: 'a', timestamp: 1000 },
      { id: 'b', role: 'assistant' as const, content: 'b', timestamp: 2000 },
    ];
    const result = syncConversationMessagesWithStore(conv(cached), 'thread-1', [
      dbMsg('c', '2026-03-09T12:00:00Z'),
    ]);
    expect(result[0].messages.map((m) => m.id)).toEqual(['c']);
    expect(result[0].messageCount).toBe(2); // count stays monotonic
  });
});

describe('selectDisplayedMessages local-provenance merge', () => {
  const storeMsg = (id: string, content: string) =>
    ({
      id,
      role: 'assistant',
      content,
      created_at: '2026-03-09T12:00:00Z',
      citations: [],
      latency_ms: 2000,
    }) as any;

  it('keeps plan and tokenUsage when the store swap drops in-memory fields', () => {
    const plan = [
      {
        step: 1,
        description: 'Search arXiv',
        tool: 'search_arxiv',
        args_hint: {},
        depends_on: [],
      },
    ];
    const result = selectDisplayedMessages({
      localMessages: [
        {
          id: 'm-1',
          role: 'assistant',
          content: 'Answer',
          timestamp: 1,
          plan,
          metadata: {
            responseTimeMs: 1800,
            tokenUsage: { input: 1200, output: 300 },
            toolsUsed: ['Searching arXiv'],
          },
        },
      ],
      storeMessages: [storeMsg('m-1', 'Answer')],
    });

    expect(result[0].plan).toEqual(plan);
    expect(result[0].metadata?.tokenUsage).toEqual({
      input: 1200,
      output: 300,
    });
    expect(result[0].metadata?.toolsUsed).toEqual(['Searching arXiv']);
    // Server latency stays canonical over the local estimate.
    expect(result[0].metadata?.responseTimeMs).toBe(2000);
  });

  it('keeps toolExecutions when the store row has none (legacy mode, M3)', () => {
    const toolExecutions = [
      {
        tool: 'search_arxiv',
        label: 'Searching arXiv',
        status: 'done' as const,
      },
    ];
    const result = selectDisplayedMessages({
      localMessages: [
        {
          id: 'm-1',
          role: 'assistant',
          content: 'Answer',
          timestamp: 1,
          toolExecutions,
        },
      ],
      storeMessages: [storeMsg('m-1', 'Answer')],
    });

    expect(result[0].toolExecutions).toEqual(toolExecutions);
  });

  it('falls back to role+content matching for optimistic messages without ids', () => {
    const result = selectDisplayedMessages({
      localMessages: [
        {
          role: 'assistant',
          content: 'Answer',
          timestamp: 1,
          metadata: { tokenUsage: { input: 10, output: 5 } },
        },
      ],
      storeMessages: [storeMsg('m-9', 'Answer')],
    });

    expect(result[0].metadata?.tokenUsage).toEqual({ input: 10, output: 5 });
  });

  it('leaves unmatched store messages untouched', () => {
    const result = selectDisplayedMessages({
      localMessages: [
        {
          id: 'other',
          role: 'assistant',
          content: 'Different turn',
          timestamp: 1,
          plan: [] as never,
          metadata: { tokenUsage: { input: 1, output: 1 } },
        },
      ],
      storeMessages: [storeMsg('m-1', 'Answer')],
    });

    expect(result[0].plan).toBeUndefined();
    expect(result[0].metadata?.tokenUsage).toBeUndefined();
  });
});

describe('isThreadSwitchPending', () => {
  const base = {
    activeThreadId: 'thread-B',
    loadingThreadId: 'thread-B',
    localMessageCount: 0,
    storeMessageCount: 0,
  };

  it('is pending while the active thread loads with nothing renderable yet', () => {
    expect(isThreadSwitchPending(base)).toBe(true);
  });

  it('is not pending when local messages exist (first send in a new thread)', () => {
    expect(isThreadSwitchPending({ ...base, localMessageCount: 1 })).toBe(
      false
    );
  });

  it('is not pending when the store already has the thread cached', () => {
    expect(isThreadSwitchPending({ ...base, storeMessageCount: 2 })).toBe(
      false
    );
  });

  it('is not pending when the in-flight load is for another thread', () => {
    expect(
      isThreadSwitchPending({ ...base, loadingThreadId: 'thread-A' })
    ).toBe(false);
  });

  it('is not pending with no load in flight', () => {
    expect(isThreadSwitchPending({ ...base, loadingThreadId: null })).toBe(
      false
    );
  });

  it('is not pending with no active thread', () => {
    expect(
      isThreadSwitchPending({
        ...base,
        activeThreadId: null,
        loadingThreadId: null,
      })
    ).toBe(false);
  });
});
