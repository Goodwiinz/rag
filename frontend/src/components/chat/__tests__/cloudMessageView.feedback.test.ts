import { describe, expect, it } from 'vitest';

import {
  mapDbMessageToChatPageMessage,
} from '../shared/cloudMessageView';
import { MessageRole, type ChatMessage } from '@/types/workspace';

function baseAssistant(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'm1',
    client_message_id: 'c1',
    role: MessageRole.ASSISTANT,
    content: 'hello',
    created_at: '2026-01-01T00:00:00Z',
    citations: [],
    attachments: [],
    ...overrides,
  } as unknown as ChatMessage;
}

describe('mapDbMessageToChatPageMessage — feedback mapping', () => {
  it('maps feedback_rating + feedback_text onto the view model', () => {
    const mapped = mapDbMessageToChatPageMessage(
      baseAssistant({ feedback_rating: 5, feedback_text: 'great' })
    );
    expect(mapped.feedback).toEqual({ rating: 5, comment: 'great' });
  });

  it('maps a negative rating with no comment', () => {
    const mapped = mapDbMessageToChatPageMessage(
      baseAssistant({ feedback_rating: 1, feedback_text: null })
    );
    expect(mapped.feedback).toEqual({ rating: 1, comment: null });
  });

  it('omits feedback when neither rating nor text is set', () => {
    const mapped = mapDbMessageToChatPageMessage(baseAssistant());
    expect(mapped.feedback).toBeUndefined();
  });
});
