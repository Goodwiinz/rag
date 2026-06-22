import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ChatMessageList } from '../ChatMessageList';

// Stub the heavy children so the test isolates the streaming-bubble gating.
// ChatBubble tags itself streaming vs committed so we can count renders of the
// same answer text.
vi.mock('../shared/ChatBubble', () => ({
  ChatBubble: ({ message, isStreaming, streamingContent }: any) => (
    <div data-testid={isStreaming ? 'streaming-bubble' : 'committed-bubble'}>
      {isStreaming ? streamingContent : message.content}
    </div>
  ),
}));
vi.mock('../shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));
vi.mock('../CommandOutputBubble', () => ({ CommandOutputBubble: () => null }));
vi.mock('@/store/chat-store', () => ({
  useChatStore: (selector: any) => selector({ streamingCitations: [] }),
}));

const baseProps = {
  activeThreadId: 't1',
  isLoading: false,
  storeStreamingContent: 'ANSWER',
  streamingTimestamp: 1,
  onRegenerate: () => {},
  onCitationClick: () => {},
};

describe('ChatMessageList streaming bubble (double-render guard)', () => {
  it('hides the streaming bubble once the committed assistant message is present', () => {
    // The post-finish window: storeIsStreaming may still be true while the
    // committed assistant answer is already in `messages`. The streamed bubble
    // must NOT also render, or the same answer paints twice.
    render(
      <ChatMessageList
        {...baseProps}
        storeIsStreaming
        messages={[
          { role: 'user', content: 'q', timestamp: 1 },
          { role: 'assistant', content: 'ANSWER', timestamp: 2 },
        ]}
      />
    );

    expect(screen.queryByTestId('streaming-bubble')).toBeNull();
    expect(screen.getAllByText('ANSWER')).toHaveLength(1);
  });

  it('shows the streaming bubble while the last committed message is the user turn', () => {
    render(
      <ChatMessageList
        {...baseProps}
        storeIsStreaming
        messages={[{ role: 'user', content: 'q', timestamp: 1 }]}
      />
    );

    expect(screen.getByTestId('streaming-bubble')).toBeTruthy();
    expect(screen.getByText('ANSWER')).toBeTruthy();
  });
});
