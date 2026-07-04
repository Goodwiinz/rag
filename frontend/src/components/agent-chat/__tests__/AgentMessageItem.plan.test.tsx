import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AgentMessageItem } from '../AgentMessageItem';
import type { AgentMessage, PlanStep } from '@/types/agent-chat';

const plan: PlanStep[] = [
  {
    step: 1,
    description: 'Search arXiv',
    tool: 'search_arxiv',
    args_hint: { query: 'transformers' },
    depends_on: [],
  },
];

function makeMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  return {
    id: 'msg-1',
    role: 'assistant',
    content: 'Here are the results.',
    timestamp: new Date(),
    ...overrides,
  };
}

describe('AgentMessageItem inline plan', () => {
  it('does not render a plan section when message has no plan', () => {
    render(<AgentMessageItem message={makeMessage()} />);
    expect(screen.queryByText('Execution plan')).not.toBeInTheDocument();
  });

  it('renders expanded while the message is streaming', () => {
    render(
      <AgentMessageItem
        message={makeMessage({ plan, isStreaming: true, content: '' })}
      />
    );
    expect(screen.getByText('Execution plan')).toBeInTheDocument();
    expect(screen.getByLabelText('Collapse execution plan')).toBeInTheDocument();
    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
  });

  it('renders collapsed once the message has finished streaming', () => {
    render(
      <AgentMessageItem message={makeMessage({ plan, isStreaming: false })} />
    );
    expect(screen.getByText('Execution plan')).toBeInTheDocument();
    expect(screen.getByLabelText('Expand execution plan')).toBeInTheDocument();
    expect(screen.queryByText('Search arXiv')).not.toBeInTheDocument();
  });

  it('does not render a plan for user messages', () => {
    render(
      <AgentMessageItem
        message={makeMessage({ role: 'user', plan, content: 'hi' })}
      />
    );
    expect(screen.queryByText('Execution plan')).not.toBeInTheDocument();
  });
});
