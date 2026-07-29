/**
 * The pre-first-token pill is the only thing on screen during a long silent
 * planner/LLM phase. Without the heartbeat reading a 62-second run showed no
 * progress at all, which reads as a hung UI.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, type RenderResult } from '@testing-library/react';

import { makeChatPageMessage } from '@/test/chatMessageFactory';
import { useChatStore } from '@/store/chat-store';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';
import { AuiMessageByIndex, formatStreamingElapsed } from '../AuiMessage';

vi.mock('@/components/chat/shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));

function renderStreamingTurn(): RenderResult {
  const messages = [
    makeChatPageMessage({ id: 'u1', role: 'user', content: 'go', timestamp: 1 }),
    makeChatPageMessage({
      runtimeId: 'a1',
      role: 'assistant',
      content: '',
      timestamp: 2,
      isStreaming: true,
    }),
  ];
  return render(
    <ChatRuntimeProvider
      messages={messages}
      isRunning
      onSend={() => {}}
      onCancel={() => {}}
    >
      <AuiMessageByIndex index={1} message={messages[1]} />
    </ChatRuntimeProvider>
  );
}

describe('streaming thinking pill elapsed time', () => {
  beforeEach(() => {
    useChatStore.setState({
      streamingContent: '',
      streamingSteps: [],
      streamingCitations: [],
      isRetrievingRag: false,
      streamingElapsedMs: null,
    });
  });

  it('renders the heartbeat elapsed time next to the phase label', () => {
    useChatStore.setState({ streamingElapsedMs: 47_000 });
    renderStreamingTurn();

    expect(screen.getByText('Reflecting')).toBeInTheDocument();
    expect(screen.getByText('· 47s')).toBeInTheDocument();
  });

  it('shows no reading before the first heartbeat', () => {
    renderStreamingTurn();

    expect(screen.getByText('Reflecting')).toBeInTheDocument();
    expect(screen.queryByText(/·\s*\d/)).not.toBeInTheDocument();
  });

  it('keeps the ticking counter out of the pill’s live announcements', () => {
    useChatStore.setState({ streamingElapsedMs: 47_000 });
    renderStreamingTurn();

    expect(screen.getByText('· 47s')).toHaveAttribute('aria-live', 'off');
  });

  it('formats elapsed readings', () => {
    expect(formatStreamingElapsed(null)).toBeNull();
    expect(formatStreamingElapsed(400)).toBeNull();
    expect(formatStreamingElapsed(15_400)).toBe('15s');
    expect(formatStreamingElapsed(62_000)).toBe('1m 02s');
    expect(formatStreamingElapsed(3_725_000)).toBe('62m 05s');
  });
});
