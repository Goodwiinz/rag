import { describe, expect, it } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { AuiToolParts } from '../AuiToolParts';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';

const doneStep: ActivityStep = {
  tool: 'search_arxiv',
  label: 'Searching arXiv',
  status: 'done',
  durationMs: 900,
  argsSummary: 'query: rag',
  resultSummary: '5 papers',
};

describe('AuiToolParts', () => {
  it('renders a ToolFallback row per tool execution', () => {
    render(<AuiToolParts messageId="m1" steps={[doneStep]} isStreaming={false} />);
    expect(
      document.querySelector('[data-slot="aui-tool-parts"]')
    ).toBeTruthy();
    // The trigger swaps between an active and a resting label, so the tool
    // name is in the DOM twice — the inactive layer is aria-hidden.
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-label"]')
    ).toHaveTextContent('Used search_arxiv');
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
      label: 'Searching arXiv',
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
      label: 'Searching arXiv',
      status: 'running',
    };
    render(
      <AuiToolParts messageId="m1" steps={[stale]} isStreaming={false} />
    );
    // cancelled reads as a struck-through resting label, never as running
    expect(
      document.querySelector('[data-slot="tool-fallback-trigger-label"]')
    ).toHaveTextContent('Cancelled search_arxiv');
    expect(document.querySelector('.tool-shimmer')).toBeNull();
  });

  it('renders one row per step', () => {
    const steps: ActivityStep[] = [
      doneStep,
      { tool: 'ingest_paper', label: 'Ingesting', status: 'error', resultSummary: 'timeout' },
    ];
    render(<AuiToolParts messageId="m1" steps={steps} isStreaming={false} />);
    expect(
      document.querySelectorAll('[data-slot="tool-fallback-root"]')
    ).toHaveLength(2);
  });
});
