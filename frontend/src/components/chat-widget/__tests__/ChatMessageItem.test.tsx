import { describe, expect, it } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { ChatMessageItem } from '../ChatMessageItem';
import type { WidgetMessage } from '@/types/chat-widget';

describe('ChatMessageItem', () => {
  const baseTimestamp = new Date('2026-03-11T14:30:00');

  it('renders user message with content', () => {
    const message: WidgetMessage = {
      id: 'msg-u1',
      role: 'user',
      content: 'What is retrieval augmented generation?',
      timestamp: baseTimestamp,
    };
    render(<ChatMessageItem message={message} />);
    expect(
      screen.getByText('What is retrieval augmented generation?')
    ).toBeInTheDocument();
  });

  it('renders assistant message with content', () => {
    const message: WidgetMessage = {
      id: 'msg-a1',
      role: 'assistant',
      content:
        'RAG combines retrieval with generation to produce grounded answers.',
      timestamp: baseTimestamp,
    };
    render(<ChatMessageItem message={message} />);
    expect(
      screen.getByText(
        'RAG combines retrieval with generation to produce grounded answers.'
      )
    ).toBeInTheDocument();
  });

  it('renders citations when present', () => {
    const message: WidgetMessage = {
      id: 'msg-a2',
      role: 'assistant',
      content: 'According to the documents...',
      timestamp: baseTimestamp,
      citations: [
        {
          documentId: 'doc-1',
          documentTitle: 'RAG Survey Paper',
          snippet: 'Retrieval augmented generation...',
        },
        {
          documentId: 'doc-2',
          documentTitle: 'Vector Database Guide',
        },
      ],
    };
    render(<ChatMessageItem message={message} />);

    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('RAG Survey Paper')).toBeInTheDocument();
    expect(screen.getByText('Vector Database Guide')).toBeInTheDocument();
  });

  it('does not render citations when absent', () => {
    const message: WidgetMessage = {
      id: 'msg-a3',
      role: 'assistant',
      content: 'No sources needed here.',
      timestamp: baseTimestamp,
    };
    render(<ChatMessageItem message={message} />);

    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
  });

  it('renders timestamp', () => {
    const message: WidgetMessage = {
      id: 'msg-t1',
      role: 'user',
      content: 'Timestamp check',
      timestamp: baseTimestamp,
    };
    render(<ChatMessageItem message={message} />);

    // toLocaleTimeString with hour: '2-digit', minute: '2-digit' produces time like "02:30 PM" or "14:30"
    const expectedTime = baseTimestamp.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    expect(screen.getByText(expectedTime)).toBeInTheDocument();
  });
});
