import { describe, expect, it } from 'vitest';
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { AuiToolParts } from '../AuiToolParts';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';

const doneStep: ActivityStep = {
  tool: 'search_arxiv',
  label: 'Search arXiv',
  status: 'done',
  durationMs: 900,
  argsSummary: 'query: rag',
  resultSummary: '5 papers',
};

describe('AuiToolParts', () => {
  it('renders a ToolFallback row per tool execution', () => {
    render(
      <AuiToolParts messageId="m1" steps={[doneStep]} isStreaming={false} />
    );
    expect(document.querySelector('[data-slot="aui-tool-parts"]')).toBeTruthy();
    // The trigger swaps between an active and a resting label, so the tool
    // name is in the DOM twice — the inactive layer is aria-hidden.
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-label"]')
    ).toHaveTextContent('Used Search arXiv');
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger"]')
    ).toHaveClass('min-h-11');
  });

  it('renders nothing for empty steps', () => {
    const { container } = render(
      <AuiToolParts messageId="m1" steps={[]} isStreaming={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('running step while streaming shimmers the active label', () => {
    const running: ActivityStep = {
      tool: 'search_arxiv',
      label: 'Search arXiv',
      status: 'running',
    };
    render(<AuiToolParts messageId="m1" steps={[running]} isStreaming />);
    // running is carried by the shimmering "Using <tool>" label, and by the
    // absence of the completion check.
    expect(document.querySelector('.tool-shimmer')).toBeTruthy();
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-check"]')
    ).toBeNull();
  });

  it('running step on a non-streaming message reads as cancelled (incomplete)', () => {
    const stale: ActivityStep = {
      tool: 'search_arxiv',
      label: 'Search arXiv',
      status: 'running',
    };
    render(<AuiToolParts messageId="m1" steps={[stale]} isStreaming={false} />);
    // cancelled reads as a struck-through resting label, never as running
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-label"]')
    ).toHaveTextContent('Cancelled Search arXiv');
    expect(document.querySelector('.tool-shimmer')).toBeNull();
  });

  it('keeps a persisted cancelled execution cancelled', () => {
    render(
      <AuiToolParts
        messageId="m1"
        steps={[
          {
            tool: 'create_project',
            label: 'Create project',
            status: 'cancelled',
          },
        ]}
        isStreaming={false}
      />
    );
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-label"]')
    ).toHaveTextContent('Cancelled Create project');
  });

  it('renders one row per step', () => {
    const steps: ActivityStep[] = [
      doneStep,
      {
        tool: 'ingest_paper',
        label: 'Ingesting',
        status: 'error',
        resultSummary: 'timeout',
      },
    ];
    render(<AuiToolParts messageId="m1" steps={steps} isStreaming={false} />);
    expect(
      document.querySelectorAll('[data-slot="tool-fallback-root"]')
    ).toHaveLength(2);
  });

  it('labels a failed tool honestly and exposes its error as an error', () => {
    const failed: ActivityStep = {
      tool: 'ingest_arxiv_papers',
      label: 'Ingest arXiv papers',
      status: 'error',
      resultSummary: 'The arXiv request timed out',
    };
    render(
      <AuiToolParts messageId="m1" steps={[failed]} isStreaming={false} />
    );

    const trigger = document.querySelector(
      '[data-slot="tool-fallback-trigger"]'
    ) as HTMLButtonElement;
    expect(trigger).toHaveTextContent('Failed Ingest arXiv papers');
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-check"]')
    ).toBeNull();

    fireEvent.click(trigger);
    expect(screen.getByText('Error:')).toBeInTheDocument();
    expect(screen.getByText('The arXiv request timed out')).toBeInTheDocument();
    expect(screen.queryByText('Result')).not.toBeInTheDocument();
  });

  it('uses the document-search renderer while the tool is live', () => {
    render(
      <AuiToolParts
        messageId="m1"
        isStreaming
        steps={[
          {
            tool: 'search_documents',
            label: 'Search documents',
            status: 'running',
            args: { query: 'agent memory' },
          },
        ]}
      />
    );

    expect(
      document.querySelector('[data-slot="search-documents-tool"]')
    ).toBeTruthy();
    expect(screen.getByText('agent memory')).toBeInTheDocument();
    expect(screen.getByText('searching…')).toBeInTheDocument();
  });
});
