import { render, screen } from '@testing-library/react';

jest.mock('@/components/ui/sidebar', () => ({
  SidebarTrigger: ({ className }: { className?: string }) => (
    <button data-testid="sidebar-trigger" className={className}>
      Toggle
    </button>
  ),
}));

import { ChatHeader } from '../ChatHeader';

describe('ChatHeader', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders breadcrumb with Dashboard / Chat', () => {
    render(<ChatHeader />);
    expect(screen.getByText('Dashboard /')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
  });

  it('does not include a workspace selector (moved to ChatSidebar)', () => {
    render(<ChatHeader />);
    expect(screen.queryByLabelText('Select workspace')).not.toBeInTheDocument();
  });

  it('exposes the command palette affordance', () => {
    render(<ChatHeader />);
    expect(screen.getByLabelText('Open command palette')).toBeInTheDocument();
  });

  it('no longer renders a connected-status clock', () => {
    jest.setSystemTime(new Date('2026-03-08T14:30:00'));
    render(<ChatHeader />);
    expect(screen.queryByTitle('Connected')).not.toBeInTheDocument();
  });

  it('shows model picker when onModelChange is provided', () => {
    render(<ChatHeader onModelChange={() => {}} selectedModelId="gpt-4o" />);
    expect(screen.getByText('GPT-4o')).toBeInTheDocument();
  });

  it('shows copy-all and export only when messages exist', () => {
    const { rerender } = render(
      <ChatHeader messages={[]} onCopyAll={() => {}} />
    );
    expect(screen.queryByLabelText('Copy all messages')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Export chat')).not.toBeInTheDocument();

    rerender(
      <ChatHeader
        messages={[{ role: 'user', content: 'hi', timestamp: Date.now() }]}
        onCopyAll={() => {}}
      />
    );
    expect(screen.getByLabelText('Copy all messages')).toBeInTheDocument();
    expect(screen.getByLabelText('Export chat')).toBeInTheDocument();
  });
});
