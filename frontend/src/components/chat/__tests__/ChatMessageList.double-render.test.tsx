import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type React from 'react';

import { ChatMessageList } from '../ChatMessageList';
import { ChatRuntimeProvider } from '../aui/ChatRuntimeProvider';
import type { ChatPageMessage } from '../shared/cloudMessageView';

// Stub the heavy children so the test isolates the streaming-bubble gating.
// ChatBubble still tags streaming bubbles; committed messages now render through
// assistant-ui MessagePrimitive via AuiMessageByIndex.
vi.mock('../shared/ChatBubble', () => ({
  ChatBubble: ({ message, isStreaming, streamingContent }: any) => (
    <div data-testid={isStreaming ? 'streaming-bubble' : 'typing-bubble'}>
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

function renderList(
  props: Omit<React.ComponentProps<typeof ChatMessageList>, 'activeThreadId'> & {
    activeThreadId?: string | null;
  }
) {
  const messages = props.messages as ChatPageMessage[];
  return render(
    <ChatRuntimeProvider
      messages={messages}
      isRunning={Boolean(props.storeIsStreaming)}
      onSend={() => {}}
      onCancel={() => {}}
    >
      <ChatMessageList activeThreadId="t1" {...props} />
    </ChatRuntimeProvider>
  );
}

describe('ChatMessageList streaming bubble (double-render guard)', () => {
  it('hides the streaming bubble once the committed assistant message is present', () => {
    // The post-finish window: storeIsStreaming may still be true while the
    // committed assistant answer is already in `messages`. The streamed bubble
    // must NOT also render, or the same answer paints twice.
    renderList({
      ...baseProps,
      storeIsStreaming: true,
      messages: [
        { role: 'user', content: 'q', timestamp: 1 },
        { role: 'assistant', content: 'ANSWER', timestamp: 2 },
      ],
    });

    expect(screen.queryByTestId('streaming-bubble')).toBeNull();
    expect(screen.getAllByText('ANSWER')).toHaveLength(1);
  });

  it('shows the streaming bubble while the last committed message is the user turn', () => {
    renderList({
      ...baseProps,
      storeIsStreaming: true,
      messages: [{ role: 'user', content: 'q', timestamp: 1 }],
    });

    expect(screen.getByTestId('streaming-bubble')).toBeTruthy();
    expect(screen.getByText('ANSWER')).toBeTruthy();
  });

  it('shows the streaming bubble during regenerate (last message is the STALE assistant answer, not the live stream)', () => {
    // Regenerate truncates local messages, so the displayed list can still end
    // in the previous assistant answer while a NEW stream is in flight. The
    // live bubble must stay visible because the stale content !== the stream.
    renderList({
      ...baseProps,
      storeIsStreaming: true,
      storeStreamingContent: 'NEW partial answer',
      messages: [
        { role: 'user', content: 'q', timestamp: 1 },
        { role: 'assistant', content: 'OLD answer', timestamp: 2 },
      ],
    });

    expect(screen.getByTestId('streaming-bubble')).toBeTruthy();
    expect(screen.getByText('NEW partial answer')).toBeTruthy();
  });
});
