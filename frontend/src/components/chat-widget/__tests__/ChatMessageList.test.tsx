import { beforeAll, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { ChatMessageList } from '../ChatMessageList';
import type { WidgetMessage } from '@/types/chat-widget';

// jsdom does not implement scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  MessageSquare: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-message-square" {...props} />
  ),
}));

// Mock ScrollArea to render children directly
vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
}));

// Mock ChatMessageItem to render content directly
vi.mock('../ChatMessageItem', () => ({
  ChatMessageItem: ({ message }: { message: WidgetMessage }) => (
    <div data-testid={`message-${message.id}`}>{message.content}</div>
  ),
}));

const mockMessages: WidgetMessage[] = [
  {
    id: 'msg1',
    role: 'user' as const,
    content: 'Hello there',
    timestamp: new Date(),
  },
  {
    id: 'msg2',
    role: 'assistant' as const,
    content: 'Hi! How can I help?',
    timestamp: new Date(),
  },
];

describe('ChatMessageList', () => {
  it('renders empty state when no messages', () => {
    render(<ChatMessageList messages={[]} isStreaming={false} />);
    expect(screen.getByText('AWAITING_INPUT')).toBeInTheDocument();
    expect(
      screen.getByText('Start a conversation to begin your research session.')
    ).toBeInTheDocument();
  });

  it('renders messages when provided', () => {
    render(<ChatMessageList messages={mockMessages} isStreaming={false} />);
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByText('Hi! How can I help?')).toBeInTheDocument();
  });

  it('shows typing indicator when streaming', () => {
    render(<ChatMessageList messages={mockMessages} isStreaming={true} />);
    const typingIndicator = screen.getByLabelText('Assistant is typing');
    expect(typingIndicator).toBeInTheDocument();

    // Verify 3 bouncing dot spans
    const dots = typingIndicator.querySelectorAll('span');
    expect(dots).toHaveLength(3);
  });

  it('does not show typing indicator when not streaming', () => {
    render(<ChatMessageList messages={mockMessages} isStreaming={false} />);
    expect(
      screen.queryByLabelText('Assistant is typing')
    ).not.toBeInTheDocument();
  });

  it('renders both user and assistant messages', () => {
    render(<ChatMessageList messages={mockMessages} isStreaming={false} />);
    expect(screen.getByTestId('message-msg1')).toBeInTheDocument();
    expect(screen.getByTestId('message-msg2')).toBeInTheDocument();
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByText('Hi! How can I help?')).toBeInTheDocument();
  });
});
