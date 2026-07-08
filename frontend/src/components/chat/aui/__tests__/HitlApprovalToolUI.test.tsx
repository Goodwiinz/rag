import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { createElement } from 'react';

import { HitlApprovalToolUI } from '../HitlApprovalToolUI';

// makeAssistantToolUI attaches the raw tool (incl. the render component) as
// `.unstable_tool`, so we can drive the renderer without a full runtime.
const Renderer = (HitlApprovalToolUI as unknown as {
  unstable_tool: { render: React.ComponentType<Record<string, unknown>> };
}).unstable_tool.render;

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

    expect(screen.getByText('ingest_arxiv_papers')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
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

  it('renders nothing once the gate is resolved', () => {
    const { container } = renderGate({
      args: { toolName: 'x', toolArgs: {} },
      approval: { id: 'a3', approved: true },
      respondToApproval: vi.fn(),
    });
    expect(container).toBeEmptyDOMElement();
  });
});
