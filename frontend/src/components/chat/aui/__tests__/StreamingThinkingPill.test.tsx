/**
 * Live message timing starts with the turn and remains mounted while answer
 * tokens arrive; the server heartbeat only corrects the local clock.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, type RenderResult } from '@testing-library/react';

import { makeChatPageMessage } from '@/test/chatMessageFactory';
import { useChatStore } from '@/store/chat-store';
import { ChatRuntimeProvider } from '../ChatRuntimeProvider';
import { AuiMessageByIndex, formatStreamingElapsed } from '../AuiMessage';

vi.mock('@/components/chat/shared/InlineAgentSummary', () => ({
  InlineAgentSummary: () => null,
}));

function renderStreamingTurn(): RenderResult {
  const messages = [
    makeChatPageMessage({
      id: 'u1',
      role: 'user',
      content: 'go',
      timestamp: 1,
    }),
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

describe('streaming reasoning panel and elapsed time', () => {
  beforeEach(() => {
    useChatStore.setState({
      streamingContent: '',
      streamingSteps: [],
      streamingProgress: [],
      streamingReasoning: '',
      streamingCitations: [],
      isRetrievingRag: false,
      streamingElapsedMs: null,
      streamingPhase: 'accepted',
      streamingStatusDetail: null,
    });
  });

  afterEach(() => vi.useRealTimers());

  it('renders message timing immediately and updates it during streaming', () => {
    vi.useFakeTimers();
    renderStreamingTurn();

    expect(
      document.querySelector('[data-slot="reasoning-panel"]')
    ).toHaveTextContent('Starting');
    expect(screen.getByText('0.0s')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(9_400));
    expect(screen.getByText('9.4s')).toBeInTheDocument();
  });

  it('renders the server-reported phase instead of guessing from the RAG toggle', () => {
    useChatStore.setState({
      isRetrievingRag: true,
      streamingPhase: 'routing',
    });
    renderStreamingTurn();

    expect(
      document.querySelector('[data-slot="reasoning-panel"]')
    ).toHaveTextContent('Choosing approach');
    expect(screen.queryByText('Reading sources')).not.toBeInTheDocument();
  });

  it('prefers the specific live activity over the coarse phase', () => {
    useChatStore.setState({
      streamingPhase: 'routing',
      streamingStatusDetail: 'Choosing the safest response path',
    });
    renderStreamingTurn();

    expect(
      document.querySelector('[data-slot="reasoning-panel"]')
    ).toHaveTextContent('Choosing the safest response path');
    expect(screen.queryByText('Choosing approach')).not.toBeInTheDocument();
  });

  it('shows every explicit server progress step', () => {
    useChatStore.setState({
      streamingProgress: [
        { phase: 'accepted', detail: 'Request accepted' },
        { phase: 'retrieving', detail: 'Reading relevant sources' },
        { phase: 'writing', detail: 'Drafting the response' },
      ],
    });
    renderStreamingTurn();

    const panel = document.querySelector('[data-slot="reasoning-panel"]');
    expect(panel).toHaveTextContent('Request accepted');
    expect(panel).toHaveTextContent('Reading relevant sources');
    expect(panel).toHaveTextContent('Drafting the response');
  });

  it('shows provider summarized reasoning separately from progress', () => {
    useChatStore.setState({
      streamingProgress: [
        { phase: 'retrieving', detail: 'Reading relevant sources' },
      ],
      streamingReasoning: 'Comparing the strongest evidence across sources.',
    });
    renderStreamingTurn();

    const panel = document.querySelector('[data-slot="reasoning-panel"]');
    expect(panel).toHaveTextContent('Reading relevant sources');
    expect(panel).toHaveTextContent('Reasoning summary');
    expect(panel).toHaveTextContent(
      'Comparing the strongest evidence across sources.'
    );
  });

  it('keeps message timing visible after answer tokens arrive', () => {
    useChatStore.setState({ streamingElapsedMs: 47_000 });
    useChatStore.setState({ streamingContent: 'Drafting the answer' });
    renderStreamingTurn();

    const timing = document.querySelector('[data-slot="message-timing"]');
    expect(
      document.querySelector('[data-slot="reasoning-panel"]')
    ).toBeTruthy();
    expect(timing).toHaveTextContent('total47.0s');
    expect(timing).toHaveAttribute('aria-live', 'off');
  });

  it('renders retrieved passages from live RAG context', () => {
    useChatStore.setState({
      streamingCitations: [
        {
          document_id: 'doc-1',
          title: 'Attention Is All You Need',
          content: 'The Transformer uses self-attention instead of recurrence.',
          score: 0.91,
        },
      ],
      isRetrievingRag: false,
    });
    renderStreamingTurn();

    const retrieval = document.querySelector('[data-slot="retrieval-chunks"]');
    expect(retrieval).toHaveTextContent('1 passage above threshold');
    expect(retrieval).toHaveTextContent('Attention Is All You Need');
    expect(retrieval).toHaveTextContent('0.91');
    expect(retrieval?.querySelector('[style]')).toHaveStyle({ width: '91%' });
  });

  it('renders a safe score when an injected context provides a string', () => {
    useChatStore.setState({
      streamingCitations: [
        {
          document_id: 'doc-1',
          title: 'Injected context',
          content: 'A context with an invalid score.',
          score: 'not-a-number' as unknown as number,
        },
      ],
      isRetrievingRag: false,
    });

    expect(() => renderStreamingTurn()).not.toThrow();
    const retrieval = document.querySelector('[data-slot="retrieval-chunks"]');
    expect(retrieval).toHaveTextContent('0.00');
    expect(retrieval?.querySelector('[style]')).toHaveStyle({ width: '0%' });
  });

  it('formats elapsed readings', () => {
    expect(formatStreamingElapsed(null)).toBeNull();
    expect(formatStreamingElapsed(400)).toBeNull();
    expect(formatStreamingElapsed(15_400)).toBe('15s');
    expect(formatStreamingElapsed(62_000)).toBe('1m 02s');
    expect(formatStreamingElapsed(3_725_000)).toBe('62m 05s');
  });
});
