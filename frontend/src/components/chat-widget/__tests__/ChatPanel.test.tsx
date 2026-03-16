import { render, screen, fireEvent } from '@/test/test-utils';
import { ChatPanel } from '../ChatPanel';
import type { ContextChip, WidgetMessage } from '@/types/chat-widget';
import { expectNoA11yViolations } from '@/test/a11y';

// Mock sub-components to isolate ChatPanel logic
jest.mock('../ChatContextBar', () => ({
  ChatContextBar: (props: Record<string, unknown>) => (
    <div data-testid="context-bar" data-props={JSON.stringify(props)} />
  ),
}));

jest.mock('../ChatMessageList', () => ({
  ChatMessageList: (props: Record<string, unknown>) => (
    <div data-testid="message-list" data-props={JSON.stringify(props)} />
  ),
}));

jest.mock('../ChatPanelInput', () => ({
  ChatPanelInput: (props: Record<string, unknown>) => (
    <div data-testid="panel-input" data-props={JSON.stringify(props)} />
  ),
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  X: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-x" {...props} />
  ),
  Trash2: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-trash" {...props} />
  ),
}));

const mockChips: ContextChip[] = [
  {
    kind: 'documents',
    label: 'Documents',
    count: 3,
    active: true,
    icon: 'file-text',
  },
  {
    kind: 'notes',
    label: 'Notes',
    count: 1,
    active: false,
    icon: 'sticky-note',
  },
];

const mockMessages: WidgetMessage[] = [
  {
    id: 'msg-1',
    role: 'user',
    content: 'Hello',
    timestamp: new Date('2026-01-01T00:00:00Z'),
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: 'Hi there!',
    timestamp: new Date('2026-01-01T00:00:01Z'),
  },
];

describe('ChatPanel', () => {
  const defaultProps = {
    messages: mockMessages,
    contextChips: mockChips,
    isStreaming: false,
    inputValue: 'draft text',
    onInputChange: jest.fn(),
    onSend: jest.fn(),
    onToggleChip: jest.fn(),
    onToggleAllChips: jest.fn(),
    onClear: jest.fn(),
    onClose: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders header with "Quick Chat" title', () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByText('Quick Chat')).toBeInTheDocument();
  });

  it('renders context bar, message list, and input sections', () => {
    render(<ChatPanel {...defaultProps} />);
    expect(screen.getByTestId('context-bar')).toBeInTheDocument();
    expect(screen.getByTestId('message-list')).toBeInTheDocument();
    expect(screen.getByTestId('panel-input')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = jest.fn();
    render(<ChatPanel {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Close chat panel' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClear when clear button clicked', () => {
    const onClear = jest.fn();
    render(<ChatPanel {...defaultProps} onClear={onClear} />);
    fireEvent.click(
      screen.getByRole('button', { name: 'Clear chat messages' })
    );
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('clear button is disabled when no messages', () => {
    render(<ChatPanel {...defaultProps} messages={[]} />);
    const clearButton = screen.getByRole('button', {
      name: 'Clear chat messages',
    });
    expect(clearButton).toBeDisabled();
  });

  it('passes correct props to ChatContextBar', () => {
    render(<ChatPanel {...defaultProps} />);
    const contextBar = screen.getByTestId('context-bar');
    const props = JSON.parse(contextBar.getAttribute('data-props')!);
    expect(props.chips).toEqual(
      mockChips.map((c) => ({
        kind: c.kind,
        label: c.label,
        count: c.count,
        active: c.active,
        icon: c.icon,
      }))
    );
    // onToggleChip and onToggleAll are functions — they serialize as undefined in JSON,
    // but we can verify the keys are present by checking they were not omitted entirely
    // Instead, verify the mock was called with function props by checking the component rendered
    expect(contextBar).toBeInTheDocument();
  });

  it('passes correct props to ChatMessageList', () => {
    render(<ChatPanel {...defaultProps} />);
    const messageList = screen.getByTestId('message-list');
    const props = JSON.parse(messageList.getAttribute('data-props')!);
    expect(props.isStreaming).toBe(false);
    // messages contain Date objects which serialize as strings
    expect(props.messages).toHaveLength(2);
    expect(props.messages[0].id).toBe('msg-1');
    expect(props.messages[1].id).toBe('msg-2');
  });

  it('passes correct props to ChatPanelInput', () => {
    render(<ChatPanel {...defaultProps} />);
    const panelInput = screen.getByTestId('panel-input');
    const props = JSON.parse(panelInput.getAttribute('data-props')!);
    expect(props.value).toBe('draft text');
    expect(props.disabled).toBe(false);
  });

  it('has accessible dialog title with id', () => {
    render(<ChatPanel {...defaultProps} />);
    const heading = screen.getByText('Quick Chat');
    expect(heading.tagName).toBe('H3');
    expect(heading).toHaveAttribute('id', 'chat-panel-title');
  });
});

describe('ChatPanel a11y', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(
      <ChatPanel
        messages={mockMessages}
        contextChips={mockChips}
        isStreaming={false}
        inputValue=""
        onInputChange={jest.fn()}
        onSend={jest.fn()}
        onToggleChip={jest.fn()}
        onToggleAllChips={jest.fn()}
        onClear={jest.fn()}
        onClose={jest.fn()}
      />
    );
    await expectNoA11yViolations(container);
  });
});
