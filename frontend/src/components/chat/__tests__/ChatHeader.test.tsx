import { render, screen } from '@testing-library/react';

// Mock sidebar trigger since it requires SidebarProvider context
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
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByText('Dashboard /')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
  });

  it('displays workspace name when provided', () => {
    const workspace = {
      id: 'ws-1',
      name: 'My Workspace',
      description: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    render(<ChatHeader currentWorkspace={workspace} />);
    expect(screen.getByText('My Workspace')).toBeInTheDocument();
  });

  it('shows fallback Workspace label when no workspace', () => {
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByText('Workspace')).toBeInTheDocument();
  });

  it('has aria-labels on workspace + command palette', () => {
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByLabelText('Select workspace')).toBeInTheDocument();
    expect(screen.getByLabelText('Open command palette')).toBeInTheDocument();
  });

  it('renders the compact connected status clock', () => {
    jest.setSystemTime(new Date('2026-03-08T14:30:00'));
    render(<ChatHeader currentWorkspace={null} />);
    // HH:MM only, 24-hour, tabular nums
    expect(screen.getByText(/\d{2}:\d{2}/)).toBeInTheDocument();
    expect(screen.getByTitle('Connected')).toBeInTheDocument();
  });

  it('shows model picker when onModelChange is provided', () => {
    render(
      <ChatHeader
        currentWorkspace={null}
        onModelChange={() => {}}
        selectedModelId="gpt-4o"
      />
    );
    expect(screen.getByText('GPT-4o')).toBeInTheDocument();
  });

  it('shows copy-all and export only when messages exist', () => {
    const { rerender } = render(
      <ChatHeader currentWorkspace={null} messages={[]} onCopyAll={() => {}} />
    );
    expect(screen.queryByLabelText('Copy all messages')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Export chat')).not.toBeInTheDocument();

    rerender(
      <ChatHeader
        currentWorkspace={null}
        messages={[{ role: 'user', content: 'hi', timestamp: Date.now() }]}
        onCopyAll={() => {}}
      />
    );
    expect(screen.getByLabelText('Copy all messages')).toBeInTheDocument();
    expect(screen.getByLabelText('Export chat')).toBeInTheDocument();
  });
});
