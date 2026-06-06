import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/components/ui/sidebar', () => ({
  SidebarTrigger: ({ className }: { className?: string }) => (
    <button data-testid="sidebar-trigger" className={className}>
      Toggle
    </button>
  ),
}));

import { ChatHeader } from '../ChatHeader';

describe('ChatHeader', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders breadcrumb with Dashboard / Chat', () => {
    render(<ChatHeader />);
    expect(screen.getByText('Dashboard /')).toBeInTheDocument();
    const chatElements = screen.getAllByText('Chat');
    expect(chatElements.length).toBeGreaterThanOrEqual(1);
  });

  it('does not include a workspace selector (moved to ChatSidebar)', () => {
    render(<ChatHeader />);
    expect(screen.queryByLabelText('Select workspace')).not.toBeInTheDocument();
  });

  it('exposes the command palette affordance', () => {
    render(<ChatHeader />);
    expect(screen.getByLabelText('Search')).toBeInTheDocument();
  });

  it('no longer renders a connected-status clock', () => {
    vi.setSystemTime(new Date('2026-03-08T14:30:00'));
    render(<ChatHeader />);
    expect(screen.queryByTitle('Connected')).not.toBeInTheDocument();
  });

  it('does not render the model picker (moved to the composer)', () => {
    render(<ChatHeader />);
    expect(screen.queryByText('GPT-4o')).not.toBeInTheDocument();
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
