import { describe, expect, it } from 'vitest';
import { hydrateThreadPreviews } from '../threadPreviewHydration';

describe('threadPreviewHydration', () => {
  it('hydrates preview text for threads that already have persisted messages', async () => {
    const conversations = [
      { id: 'thread-1', title: 'One', messages: [], updatedAt: 1 },
      { id: 'thread-2', title: 'Two', messages: [], updatedAt: 2 },
    ];

    const threads = [
      {
        id: 'thread-1',
        message_count: 2,
      },
      {
        id: 'thread-2',
        message_count: 0,
      },
    ] as any;

    const result = await hydrateThreadPreviews(
      conversations,
      threads,
      async (threadId) => {
        expect(threadId).toBe('thread-1');
        return {
          messages: [
            { role: 'user', content: 'older message' },
            { role: 'assistant', content: 'persisted preview' },
          ],
        };
      }
    );

    expect(result[0].previewText).toBe('persisted preview');
    expect(result[0].messageCount).toBe(2);
    expect(result[1].previewText).toBeUndefined();
    expect(result[1].messageCount).toBe(0);
  });

  it('keeps conversations unchanged when preview fetch fails', async () => {
    const conversations = [
      { id: 'thread-1', title: 'One', messages: [], updatedAt: 1 },
    ];

    const result = await hydrateThreadPreviews(
      conversations,
      [{ id: 'thread-1', message_count: 1 } as any],
      async () => {
        throw new Error('network');
      }
    );

    expect(result).toEqual([
      {
        id: 'thread-1',
        title: 'One',
        messages: [],
        updatedAt: 1,
        messageCount: 1,
        previewText: undefined,
      },
    ]);
  });
});
