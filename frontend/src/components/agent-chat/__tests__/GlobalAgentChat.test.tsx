import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

  it('shows panel when opened', () => {
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Agent chat panel')).toBeInTheDocument();
  });

  it('shows sidebar when expanded', () => {
    useAgentChatStore.getState().openSidebar();
    render(<GlobalAgentChat />);
    expect(screen.getByLabelText('Agent chat sidebar')).toBeInTheDocument();
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
