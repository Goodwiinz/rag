import { beforeEach, describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentFAB } from '../AgentFAB';
import { useAgentChatStore } from '@/store/agentChatStore';

describe('AgentFAB', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  it('renders open button when closed', () => {
    render(<AgentFAB />);
    expect(screen.getByLabelText('Open agent chat')).toBeInTheDocument();
  });

  it('renders close button when open', () => {
    useAgentChatStore.getState().openPanel();
    render(<AgentFAB />);
    expect(screen.getByLabelText('Close agent chat')).toBeInTheDocument();
  });

  it('toggles on click', () => {
    render(<AgentFAB />);
    fireEvent.click(screen.getByLabelText('Open agent chat'));
    expect(useAgentChatStore.getState().uiMode).toBe('panel');
  });

  it('shows unread badge when hasUnread and closed', () => {
    useAgentChatStore.setState({ hasUnread: true });
    const { container } = render(<AgentFAB />);
    expect(container.querySelector('.bg-destructive')).toBeInTheDocument();
  });
});
