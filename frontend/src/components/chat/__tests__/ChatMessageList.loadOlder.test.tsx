import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type React from 'react';

import { ChatMessageList } from '../ChatMessageList';
import { ChatRuntimeProvider } from '../aui/ChatRuntimeProvider';
import type { ChatPageMessage } from '../shared/cloudMessageView';
import { makeChatPageMessage } from '@/test/chatMessageFactory';

// Regression test carried over from fix/chat-loading-consistency (the host
// double-render test file was retired with the legacy streaming path in #1100).
// ChatMessageList's own load-older controls are gated on !isVirtualized, so the
// virtualized transcript must show exactly ONE control — the one
// VirtualizedMessageList renders — not two.
vi.mock('../shared/ChatBubble', () => ({
  ChatBubble: ({ message }: any) => <div>{message.content}</div>,
}));
vi.mock('../shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));
vi.mock('../CommandOutputBubble', () => ({ CommandOutputBubble: () => null }));
vi.mock('../VirtualizedMessageList', () => ({
  VirtualizedMessageList: ({ hasMore, onLoadOlder }: any) =>
    hasMore ? <button onClick={onLoadOlder}>Load older messages</button> : null,
}));
vi.mock('@/store/chat-store', () => ({
  useChatStore: (selector: any) => selector({ streamingCitations: [] }),
}));

const baseProps = {
  activeThreadId: 't1',
  isLoading: false,
  storeStreamingContent: '',
  streamingTimestamp: 1,
  onRegenerate: () => {},
  onCitationClick: () => {},
};

function renderList(
  props: Omit<
    React.ComponentProps<typeof ChatMessageList>,
    'activeThreadId'
  > & {
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

describe('ChatMessageList load-older controls', () => {
  it('renders one load-older control after switching to the virtualized transcript', () => {
    renderList({
      ...baseProps,
      storeIsStreaming: false,
      hasMore: true,
      onLoadOlder: () => {},
      messages: Array.from({ length: 76 }, (_, index) =>
        makeChatPageMessage({
          id: `m-${index}`,
          role: 'user',
          content: `message ${index}`,
          timestamp: index,
        })
      ),
    });

    expect(screen.getAllByText('Load older messages')).toHaveLength(1);
  });
});
