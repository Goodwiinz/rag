import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
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
    expect(screen.getByText(/search_arxiv/)).toBeInTheDocument();
  });

  it('renders nothing for empty steps', () => {
    const { container } = render(
      <AuiToolParts messageId="m1" steps={[]} isStreaming={false} />
    );
    expect(container).toBeEmptyDOMElement();
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
