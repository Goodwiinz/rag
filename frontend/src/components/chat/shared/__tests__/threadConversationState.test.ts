import { describe, expect, it } from 'vitest';
import { upsertConversationFromThread } from '../threadConversationState';

describe('threadConversationState', () => {
  it('prepends a missing deep-linked thread into the conversation list', () => {
    const result = upsertConversationFromThread(
      [
        {
          id: 'thread-1',
          title: 'Existing',
          messages: [],
          createdAt: 1,
          updatedAt: 1,
          threadId: 'thread-1',
          conversationId: 'conv-1',
        },
      ],
      {
        id: 'thread-99',
        title: 'Deep linked',
        conversation_id: 'conv-1',
        created_at: '2026-03-09T12:00:00Z',
        updated_at: '2026-03-09T12:05:00Z',
        message_count: 2,
        status: 'active',
        last_message_at: '2026-03-09T12:01:00Z',
        token_count: 10,
      } as any,
      [
        { id: 'm-1', role: 'user', content: 'Question', timestamp: 1 },
        { id: 'm-2', role: 'assistant', content: 'Answer', timestamp: 2 },
      ]
    );

    expect(result[0].id).toBe('thread-99');
    expect(result[0].messages.map((message) => message.content)).toEqual([
      'Question',
      'Answer',
    ]);
    expect(result[0].previewText).toBe('Answer');
    expect(result[0].messageCount).toBe(2);
  });

  it('uses server preview metadata when no message page is loaded', () => {
    const result = upsertConversationFromThread(
      [],
      {
        id: 'thread-99',
        title: 'Deep linked',
        conversation_id: 'conv-1',
        status: 'active',
        last_message_at: '2026-03-09T12:01:00Z',
        last_message_preview: 'Bounded preview',
        message_count: 1000,
        token_count: 10,
        created_at: '2026-03-09T12:00:00Z',
        updated_at: '2026-03-09T12:05:00Z',
      },
      []
    );

    expect(result[0].messages).toEqual([]);
    expect(result[0].previewText).toBe('Bounded preview');
    expect(result[0].messageCount).toBe(1000);
  });
});
