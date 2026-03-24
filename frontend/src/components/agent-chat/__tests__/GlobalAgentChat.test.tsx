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

jest.mock('react-markdown', () => (props: any) => <div>{props.children}</div>);
jest.mock('react-syntax-highlighter', () => ({
  Prism: (props: any) => <div>{props.children}</div>,
  PrismLight: (props: any) => <div>{props.children}</div>,
  default: (props: any) => <div>{props.children}</div>,
}));
jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: {},
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
    useAgentChatStore.getState().openPanel();
    render(<GlobalAgentChat />);
    expect(await screen.findByText('AI Research Agent')).toBeInTheDocument();
  });

  it('shows sidebar when expanded', async () => {
    useAgentChatStore.getState().openSidebar();
    render(<GlobalAgentChat />);
    expect(await screen.findByText('AI Research Agent')).toBeInTheDocument();
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
