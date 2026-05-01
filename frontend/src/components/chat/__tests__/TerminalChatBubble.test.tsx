import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TerminalChatBubble } from '../shared/TerminalChatBubble';

vi.mock('../CitationRenderer', () => ({
  CitationRenderer: ({ content }: { content: string }) => <p>{content}</p>,
}));

describe('TerminalChatBubble regenerate action', () => {
  it('does NOT show retry on user messages', () => {
    render(
      <TerminalChatBubble
        message={{ role: 'user', content: 'hi', timestamp: Date.now() }}
        index={0}
        onRetry={() => {}}
      />
    );
    expect(screen.queryByLabelText(/regenerate/i)).not.toBeInTheDocument();
  });

  it('does NOT show retry on assistant messages without onRetry', () => {
    render(
      <TerminalChatBubble
        message={{ role: 'assistant', content: 'hi', timestamp: Date.now() }}
        index={0}
      />
    );
    expect(screen.queryByLabelText(/regenerate/i)).not.toBeInTheDocument();
  });

  it('calls onRetry when regenerate button clicked on assistant message', () => {
    const onRetry = vi.fn();
    render(
      <TerminalChatBubble
        message={{ role: 'assistant', content: 'hi', timestamp: Date.now() }}
        index={0}
        onRetry={onRetry}
      />
    );
    fireEvent.click(screen.getByLabelText(/regenerate/i));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
