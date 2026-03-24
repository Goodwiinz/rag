import React from 'react';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { GlobalAgentChat } from '../GlobalAgentChat';
import { useAgentChatStore } from '@/store/agentChatStore';

// Mock usePageContext
jest.mock('@/hooks/usePageContext', () => ({
  usePageContext: () => ({ type: 'overview', label: 'Overview' }),
}));

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
  useParams: () => ({}),
}));

describe('GlobalAgentChat', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  it('renders FAB by default', () => {
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Open agent chat')).toBeInTheDocument();
  });

  it('shows panel when opened', async () => {
    render(<GlobalAgentChat />);

    // Using act for state updates that affect rendering
    await waitFor(() => {
      useAgentChatStore.getState().openPanel();
    });

    // We fall back to the empty state message which is definitely rendered inside the panel
    const emptyStateMessage = await screen.findByText('AI Research Agent');
    expect(emptyStateMessage).toBeInTheDocument();
  });

  it('shows sidebar when expanded', async () => {
    useAgentChatStore.getState().openSidebar();
    render(<GlobalAgentChat />);
    const sidebar = await screen.findByLabelText('Agent chat sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  it('shows empty state message when no messages', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    expect(screen.getByText('AI Research Agent')).toBeInTheDocument();
  });

  it('closes on Escape key', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useAgentChatStore.getState().uiMode).toBe('closed');
  });
});
