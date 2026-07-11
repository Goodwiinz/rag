import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useAgentChatStore } from '@/store/agentChatStore';
import { AgentInput } from '../AgentInput';

describe('AgentInput', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
  });

  it('disables composition while the selected thread is loading', () => {
    useAgentChatStore.setState({ isLoadingMessages: true });

    render(
      <AgentInput
        value="queued prompt"
        onChange={vi.fn()}
        onSend={vi.fn()}
      />
    );

    expect(screen.getByPlaceholderText('Ask the agent...')).toBeDisabled();
    expect(screen.getByLabelText('Send message')).toBeDisabled();
  });
});
