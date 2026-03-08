import { fireEvent, render, screen } from '@testing-library/react';
import { TerminalChatBubble } from '../TerminalChatBubble';

jest.mock('../../CitationRenderer', () => ({
  CitationRenderer: ({ content }: { content: string }) => <p>{content}</p>,
}));

describe('TerminalChatBubble', () => {
  it('renders user badge and message content', () => {
    render(
      <TerminalChatBubble
        message={{
          role: 'user',
          content: 'How does this work?',
          timestamp: Date.now(),
        }}
        index={0}
      />
    );

    expect(screen.getByText('QUERY')).toBeInTheDocument();
    expect(screen.getByText('How does this work?')).toBeInTheDocument();
  });

  it('renders streaming cursor for assistant streaming state', () => {
    const { container } = render(
      <TerminalChatBubble
        message={{
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
        }}
        index={0}
        isStreaming
        streamingContent="Partial response"
      />
    );

    expect(
      container.querySelector('[data-testid="streaming-cursor"]')
    ).toBeInTheDocument();
  });

  it('invokes citation click handler from citation chips', () => {
    const onCitationClick = jest.fn();
    const citations = [
      {
        documentId: 'doc-1',
        title: 'A Foundational Paper',
        score: 0.91,
      },
    ];

    render(
      <TerminalChatBubble
        message={{
          role: 'assistant',
          content: 'See source [1] for details.',
          timestamp: Date.now(),
          citations,
        }}
        index={0}
        onCitationClick={onCitationClick}
      />
    );

    fireEvent.click(
      screen.getByRole('button', { name: /a foundational paper/i })
    );

    expect(onCitationClick).toHaveBeenCalledTimes(1);
    expect(onCitationClick).toHaveBeenCalledWith(citations, citations[0]);
  });
});
