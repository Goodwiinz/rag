import { render, screen, fireEvent } from '@/test/test-utils';
import { ChatContextBar } from '../ChatContextBar';
import type { ContextChip } from '@/types/chat-widget';
import { expectNoA11yViolations } from '@/test/a11y';

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  FileText: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-file-text" {...props} />
  ),
  StickyNote: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-sticky-note" {...props} />
  ),
  BookOpen: (props: React.SVGAttributes<SVGElement>) => (
    <svg data-testid="icon-book-open" {...props} />
  ),
}));

// Mock tooltip (renders children directly without Radix portal overhead)
jest.mock('@/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  TooltipTrigger: ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <>{children}</>,
}));

const mockChips: ContextChip[] = [
  {
    kind: 'documents' as const,
    label: 'Documents',
    count: 3,
    active: true,
    icon: 'file-text' as const,
  },
  {
    kind: 'notes' as const,
    label: 'Notes',
    count: 2,
    active: false,
    icon: 'sticky-note' as const,
  },
  {
    kind: 'bibliography' as const,
    label: 'Bibliography',
    count: 0,
    active: false,
    icon: 'book-open' as const,
  },
];

describe('ChatContextBar', () => {
  const defaultProps = {
    chips: mockChips,
    onToggleChip: jest.fn(),
    onToggleAll: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders "Chatting with:" label', () => {
    render(<ChatContextBar {...defaultProps} />);
    expect(screen.getByText('Chatting with:')).toBeInTheDocument();
  });

  it('renders all context chips with labels and counts', () => {
    render(<ChatContextBar {...defaultProps} />);
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Bibliography')).toBeInTheDocument();
    // Documents has count 3 and Notes has count 2; Bibliography count is 0 so no count rendered
    expect(screen.getByText('(3)')).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
    expect(screen.queryByText('(0)')).not.toBeInTheDocument();
  });

  it('calls onToggleChip when chip clicked', () => {
    const onToggleChip = jest.fn();
    render(<ChatContextBar {...defaultProps} onToggleChip={onToggleChip} />);

    fireEvent.click(
      screen.getByRole('button', { name: /Disable Documents context/i })
    );
    expect(onToggleChip).toHaveBeenCalledWith('documents');

    fireEvent.click(
      screen.getByRole('button', { name: /Enable Notes context/i })
    );
    expect(onToggleChip).toHaveBeenCalledWith('notes');
  });

  it('renders "All" button that toggles all chips', () => {
    const onToggleAll = jest.fn();
    render(<ChatContextBar {...defaultProps} onToggleAll={onToggleAll} />);

    const allButton = screen.getByText('All');
    expect(allButton).toBeInTheDocument();

    // Not all chips are active, so clicking All should enable all (pass true)
    fireEvent.click(allButton);
    expect(onToggleAll).toHaveBeenCalledWith(true);
  });

  it('shows active styling for enabled chips', () => {
    render(<ChatContextBar {...defaultProps} />);
    const documentsButton = screen.getByRole('button', {
      name: /Disable Documents context/i,
    });
    expect(documentsButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows inactive styling for disabled chips', () => {
    render(<ChatContextBar {...defaultProps} />);
    const notesButton = screen.getByRole('button', {
      name: /Enable Notes context/i,
    });
    expect(notesButton).toHaveAttribute('aria-pressed', 'false');

    const bibButton = screen.getByRole('button', {
      name: /Enable Bibliography context/i,
    });
    expect(bibButton).toHaveAttribute('aria-pressed', 'false');
  });
});

describe('ChatContextBar a11y', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(
      <ChatContextBar
        chips={mockChips}
        onToggleChip={jest.fn()}
        onToggleAll={jest.fn()}
      />
    );
    await expectNoA11yViolations(container);
  });
});
