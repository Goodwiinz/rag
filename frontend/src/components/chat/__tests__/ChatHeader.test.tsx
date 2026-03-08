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

  it('shows fallback text when no workspace', () => {
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByText('Fresh Test Workspace')).toBeInTheDocument();
  });

  it('has aria-labels on icon buttons', () => {
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByLabelText('Terminal')).toBeInTheDocument();
    expect(screen.getByLabelText('Settings')).toBeInTheDocument();
    expect(screen.getByLabelText('Select workspace')).toBeInTheDocument();
  });

  it('displays the clock time', () => {
    jest.setSystemTime(new Date('2026-03-08T14:30:00'));
    render(<ChatHeader currentWorkspace={null} />);
    expect(screen.getByText(/LTC/)).toBeInTheDocument();
  });
});
