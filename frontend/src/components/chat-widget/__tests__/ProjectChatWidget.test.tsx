import { render, screen, fireEvent } from '@/test/test-utils';
import { ProjectChatWidget } from '../ProjectChatWidget';

// Mock ChatPanel sub-component
jest.mock('../ChatPanel', () => ({
  ChatPanel: (props: Record<string, unknown>) => (
    <div data-testid="chat-panel" data-props={JSON.stringify(props)} />
  ),
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  MessageSquare: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-message-square" {...props} />
  ),
  X: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-x" {...props} />
  ),
}));

const mockWidget = {
  isOpen: false,
  messages: [],
  contextChips: [],
  isStreaming: false,
  inputValue: '',
  hasUnread: false,
  threadId: null,
  conversationId: null,
  open: jest.fn(),
  close: jest.fn(),
  toggle: jest.fn(),
  toggleChip: jest.fn(),
  toggleAllChips: jest.fn(),
  setInputValue: jest.fn(),
  sendMessage: jest.fn().mockResolvedValue(undefined),
  clearMessages: jest.fn(),
};

jest.mock('@/hooks/useProjectChatWidget', () => ({
  useProjectChatWidget: jest.fn(() => mockWidget),
}));

describe('ProjectChatWidget', () => {
  const defaultProps = {
    projectId: 'proj-123',
    activeTab: 'documents' as const,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset mockWidget to defaults
    mockWidget.isOpen = false;
    mockWidget.hasUnread = false;
    mockWidget.messages = [];
    mockWidget.contextChips = [];
    mockWidget.isStreaming = false;
    mockWidget.inputValue = '';
  });

  it('renders FAB button', () => {
    render(<ProjectChatWidget {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: 'Open project chat' })
    ).toBeInTheDocument();
  });

  it('does not render panel when closed', () => {
    mockWidget.isOpen = false;
    render(<ProjectChatWidget {...defaultProps} />);
    expect(screen.queryByTestId('chat-panel')).not.toBeInTheDocument();
  });

  it('renders panel when open', () => {
    mockWidget.isOpen = true;
    render(<ProjectChatWidget {...defaultProps} />);
    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
  });

  it('FAB calls toggle when clicked', () => {
    render(<ProjectChatWidget {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open project chat' }));
    expect(mockWidget.toggle).toHaveBeenCalledTimes(1);
  });

  it('FAB shows X icon when panel open', () => {
    mockWidget.isOpen = true;
    render(<ProjectChatWidget {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: 'Close project chat' })
    ).toBeInTheDocument();
    expect(screen.getByTestId('icon-x')).toBeInTheDocument();
  });

  it('FAB shows MessageSquare icon when panel closed', () => {
    mockWidget.isOpen = false;
    render(<ProjectChatWidget {...defaultProps} />);
    expect(
      screen.getByRole('button', { name: 'Open project chat' })
    ).toBeInTheDocument();
    expect(screen.getByTestId('icon-message-square')).toBeInTheDocument();
  });

  it('renders unread badge when hasUnread is true', () => {
    mockWidget.hasUnread = true;
    mockWidget.isOpen = false;
    const { container } = render(<ProjectChatWidget {...defaultProps} />);
    const badge = container.querySelector('.bg-destructive');
    expect(badge).toBeInTheDocument();
  });

  it('does not render unread badge when hasUnread is false', () => {
    mockWidget.hasUnread = false;
    const { container } = render(<ProjectChatWidget {...defaultProps} />);
    const badge = container.querySelector('.bg-destructive');
    expect(badge).not.toBeInTheDocument();
  });

  it('renders mobile backdrop when panel open', () => {
    mockWidget.isOpen = true;
    const { container } = render(<ProjectChatWidget {...defaultProps} />);
    const backdrop = container.querySelector('.sm\\:hidden');
    expect(backdrop).toBeInTheDocument();
  });

  it('does not render mobile backdrop when panel closed', () => {
    mockWidget.isOpen = false;
    const { container } = render(<ProjectChatWidget {...defaultProps} />);
    const backdrop = container.querySelector('.sm\\:hidden');
    expect(backdrop).not.toBeInTheDocument();
  });

  it('backdrop click calls close', () => {
    mockWidget.isOpen = true;
    const { container } = render(<ProjectChatWidget {...defaultProps} />);
    const backdrop = container.querySelector('.sm\\:hidden');
    expect(backdrop).toBeInTheDocument();
    fireEvent.click(backdrop!);
    expect(mockWidget.close).toHaveBeenCalledTimes(1);
  });

  it('panel has role="dialog"', () => {
    mockWidget.isOpen = true;
    render(<ProjectChatWidget {...defaultProps} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('panel has aria-labelledby="chat-panel-title"', () => {
    mockWidget.isOpen = true;
    render(<ProjectChatWidget {...defaultProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-labelledby', 'chat-panel-title');
  });

  it('Escape key calls close when panel open', () => {
    mockWidget.isOpen = true;
    render(<ProjectChatWidget {...defaultProps} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(mockWidget.close).toHaveBeenCalledTimes(1);
  });
});
