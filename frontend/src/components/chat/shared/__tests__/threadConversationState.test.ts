import { describe, expect, it } from 'vitest';
import { upsertConversationFromThreadDetail } from '../threadConversationState';

describe('threadConversationState', () => {
  it('prepends a missing deep-linked thread into the conversation list', () => {
    const result = upsertConversationFromThreadDetail(
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
        messages: [
          {
            id: 'm-1',
            role: 'user',
            content: 'Question',
            created_at: '2026-03-09T12:00:00Z',
            citations: [],
          },
          {
            id: 'm-2',
            role: 'assistant',
            content: 'Answer',
            created_at: '2026-03-09T12:01:00Z',
            citations: [],
          },
        ],
      } as any,
      (message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        timestamp: new Date(message.created_at).getTime(),
      })
    );

    expect(result[0].id).toBe('thread-99');
    expect(result[0].messages.map((message) => message.content)).toEqual([
      'Question',
      'Answer',
    ]);
    expect(result[0].previewText).toBe('Answer');
    expect(result[0].messageCount).toBe(2);
  });
});
