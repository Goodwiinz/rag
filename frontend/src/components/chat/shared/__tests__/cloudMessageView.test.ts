import { describe, expect, it } from 'vitest';
import {
  mapStoreMessagesToChatMessages,
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '../cloudMessageView';

describe('cloudMessageView', () => {
  it('maps persisted store messages into chat page message shape', () => {
    const result = mapStoreMessagesToChatMessages([
      {
        id: 'm-1',
        role: 'assistant',
        content: 'Answer',
        created_at: '2026-03-09T12:00:00Z',
        citations: [{ document_title: 'Doc 1', score: 0.8 }],
      } as any,
    ]);

    expect(result[0].role).toBe('assistant');
    expect(result[0].content).toBe('Answer');
    expect(result[0].citations?.[0].title).toBe('Doc 1');
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

    const result = syncConversationMessagesWithStore(conversations, 'thread-1', [
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
    ]);

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
