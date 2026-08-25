import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { createElement } from 'react';

import { HitlApprovalToolUI } from '../HitlApprovalToolUI';

// makeAssistantToolUI attaches the raw tool (incl. the render component) as
// `.unstable_tool`, so we can drive the renderer without a full runtime.
const Renderer = (
  HitlApprovalToolUI as unknown as {
    unstable_tool: { render: React.ComponentType<Record<string, unknown>> };
  }
).unstable_tool.render;

function renderGate(props: Record<string, unknown>) {
  return render(createElement(Renderer, props));
}

describe('HitlApprovalToolUI', () => {
  it('renders the gate and routes Approve to respondToApproval', () => {
    const respondToApproval = vi.fn();
    renderGate({
      args: { toolName: 'ingest_arxiv_papers', toolArgs: { n: 2 } },
      approval: { id: 'a1' }, // approved undefined = pending
      respondToApproval,
    });

    expect(screen.getByText('Ingest arXiv papers')).toBeInTheDocument();
    const approve = screen.getByRole('button', { name: 'Approve' });
    expect(approve).toHaveClass('min-h-11');
    expect(approve).toHaveAttribute('type', 'button');
    fireEvent.click(approve);
    expect(respondToApproval).toHaveBeenCalledWith({ approved: true });
  });

  it('routes Deny to respondToApproval and latches against double-submit', () => {
    const respondToApproval = vi.fn();
    renderGate({
      args: { toolName: 'create_draft', toolArgs: {} },
      approval: { id: 'a2' },
      respondToApproval,
    });

    const deny = screen.getByRole('button', { name: 'Deny' });
    fireEvent.click(deny);
    fireEvent.click(deny); // second click must be ignored (submitted latch)
    expect(respondToApproval).toHaveBeenCalledTimes(1);
    expect(respondToApproval).toHaveBeenCalledWith({ approved: false });
  });

  it('shows every action covered by a multi-tool approval', () => {
    renderGate({
      args: {
        tools: [
          { name: 'create_project', args: { name: 'RAG audit' } },
          {
            name: 'create_project_note',
            args: { title: 'Findings', project_id: 'p1' },
          },
        ],
      },
      approval: { id: 'multi-1' },
      respondToApproval: vi.fn(),
    });

    expect(
      screen.getByText('2 actions.', { exact: false })
    ).toBeInTheDocument();
    expect(screen.getByText('Create project')).toBeInTheDocument();
    expect(screen.getByText('Save project note')).toBeInTheDocument();
    expect(screen.getByText('project id')).toBeInTheDocument();
  });

  it('unlocks when a failed or nested gate is re-armed with a new id', () => {
    const respondToApproval = vi.fn();
    const { rerender } = renderGate({
      args: { tools: [{ name: 'create_project', args: {} }] },
      approval: { id: 'attempt-1' },
      respondToApproval,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(screen.getByRole('button', { name: 'Processing…' })).toBeDisabled();

    rerender(
      createElement(Renderer, {
        args: { tools: [{ name: 'create_project_note', args: {} }] },
        approval: { id: 'attempt-2' },
        respondToApproval,
      })
    );
    expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled();
    expect(screen.getByText('Save project note')).toBeInTheDocument();
  });

  it('renders nothing once the gate is resolved', () => {
    const { container } = renderGate({
      args: { toolName: 'x', toolArgs: {} },
      approval: { id: 'a3', approved: true },
      respondToApproval: vi.fn(),
    });
    expect(container).toBeEmptyDOMElement();
  });
});
