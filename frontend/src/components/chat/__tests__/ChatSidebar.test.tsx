import { fireEvent, render, screen } from '@testing-library/react';
import { ChatSidebar } from '../ChatSidebar';

const mockConversations = [
  {
    id: 'conv-1',
    title: 'Alpha Chat',
    messages: [{ role: 'user', content: 'Hello world' }],
    threadId: 'thread-1',
    updatedAt: Date.now() - 60000,
    messageCount: 1,
  },
  {
    id: 'conv-2',
    title: 'Beta Discussion',
    messages: [
      {
        role: 'assistant',
        content: 'This is a longer message that should be truncated',
      },
    ],
    threadId: 'thread-2',
    updatedAt: Date.now() - 3600000,
    messageCount: 1,
  },
  {
    id: 'conv-3',
    title: 'Gamma Query',
    messages: [],
    threadId: 'thread-3',
    updatedAt: Date.now() - 86400000,
    messageCount: 0,
  },
];

describe('ChatSidebar', () => {
  const defaultProps = {
    conversations: mockConversations,
    activeId: null,
    onSelect: jest.fn(),
    onNew: jest.fn(),
  };

  it('renders all conversations', () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText('Alpha Chat')).toBeInTheDocument();
    expect(screen.getByText('Beta Discussion')).toBeInTheDocument();
    expect(screen.getByText('Gamma Query')).toBeInTheDocument();
  });

  it('shows correct count badge', () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('calls onNew when NEW SESSION button is clicked', () => {
    render(<ChatSidebar {...defaultProps} />);
    fireEvent.click(screen.getByText('NEW SESSION'));
    expect(defaultProps.onNew).toHaveBeenCalledTimes(1);
  });

  it('calls onSelect when a conversation is clicked', () => {
    render(<ChatSidebar {...defaultProps} />);
    fireEvent.click(screen.getByText('Alpha Chat'));
    expect(defaultProps.onSelect).toHaveBeenCalledWith('conv-1');
  });

  it('filters conversations by search query', () => {
    render(<ChatSidebar {...defaultProps} />);
    const searchInput = screen.getByPlaceholderText('Search Logs...');
    fireEvent.change(searchInput, { target: { value: 'alpha' } });

    expect(screen.getByText('Alpha Chat')).toBeInTheDocument();
    expect(screen.queryByText('Beta Discussion')).not.toBeInTheDocument();
    expect(screen.queryByText('Gamma Query')).not.toBeInTheDocument();
    // Count badge should update
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('shows "No messages yet" for empty conversations', () => {
    render(<ChatSidebar {...defaultProps} />);
    const noMsgElements = screen.getAllByText('No messages yet');
    expect(noMsgElements.length).toBeGreaterThan(0);
  });

  it('shows a message-count fallback for persisted threads without a loaded preview', () => {
    render(
      <ChatSidebar
        {...defaultProps}
        conversations={[
          {
            id: 'conv-4',
            title: 'Count Only',
            messages: [],
            updatedAt: Date.now(),
            messageCount: 3,
          },
        ]}
      />
    );

    expect(screen.getByText('3 messages')).toBeInTheDocument();
  });

  it('shows preview text even when full messages are not loaded yet', () => {
    render(
      <ChatSidebar
        {...defaultProps}
        conversations={[
          {
            id: 'conv-4',
            title: 'Preview Only',
            messages: [],
            previewText: 'Persisted preview from thread list',
            updatedAt: Date.now(),
            messageCount: 3,
          },
        ]}
      />
    );

    expect(
      screen.getByText(/Persisted preview from thread/)
    ).toBeInTheDocument();
  });

  it('shows provided message count for active conversations', () => {
    render(
      <ChatSidebar
        {...defaultProps}
        activeId="conv-4"
        conversations={[
          {
            id: 'conv-4',
            title: 'Preview Only',
            messages: [],
            previewText: 'Persisted preview from thread list',
            updatedAt: Date.now(),
            messageCount: 3,
          },
        ]}
      />
    );

    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('truncates long preview text with ellipsis', () => {
    render(<ChatSidebar {...defaultProps} />);
    // "This is a longer message that should be truncated" is > 30 chars
    expect(
      screen.getByText(/This is a longer message that \.\.\.$/)
    ).toBeInTheDocument();
  });

  it('highlights active conversation', () => {
    render(<ChatSidebar {...defaultProps} activeId="conv-1" />);
    // Active conversation should show message count
    expect(screen.getByText('1')).toBeInTheDocument();
  });
});
