/**
 * R4-L20: ToolExecutionGroupCard renders for 2+ executions of the same tool.
 * It branched only on allCompleted/anyFailed, so a 'cancelled' execution
 * (settled by stopGeneration / confirmAction supersede) matched neither arm
 * and the group kept spinning forever on an already-stopped turn.
 */
import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AgentMessageItem } from '../AgentMessageItem';
import type { AgentMessage, ToolExecution } from '@/types/agent-chat';

function makeExecutions(status: ToolExecution['status']): ToolExecution[] {
  return [
    {
      id: 'te-1',
      toolName: 'add_document_to_project',
      toolDisplayName: 'Add Document To Project',
      args: {},
      status,
    },
    {
      id: 'te-2',
      toolName: 'add_document_to_project',
      toolDisplayName: 'Add Document To Project',
      args: {},
      status,
    },
  ];
}

function makeMessage(toolExecutions: ToolExecution[]): AgentMessage {
  return {
    id: 'msg-1',
    role: 'assistant',
    content: 'Stopped.',
    timestamp: new Date(),
    toolExecutions,
  };
}

describe('AgentMessageItem tool group card (R4-L20)', () => {
  it('does not spin when every execution in the group is cancelled', () => {
    const { container } = render(
      <AgentMessageItem message={makeMessage(makeExecutions('cancelled'))} />
    );
    expect(container.querySelector('.animate-spin')).toBeNull();
    expect(
      screen.getByLabelText('Expand 2 Add Document To Project executions')
    ).toBeInTheDocument();
  });

  it('still spins while the group is genuinely running', () => {
    const { container } = render(
      <AgentMessageItem message={makeMessage(makeExecutions('running'))} />
    );
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
