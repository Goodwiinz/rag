import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ToolStrip, getToolStripProps } from '../ToolStrip';
import type { ChatPageMessage } from '../cloudMessageView';

function makeMessage(
  overrides: Partial<ChatPageMessage> = {}
): ChatPageMessage {
  return {
    runtimeId: 'r1',
    source: 'optimistic',
    role: 'assistant',
    content: 'An answer',
    timestamp: Date.now(),
    metadata: { responseTimeMs: 4200 },
    ...overrides,
  };
}

describe('getToolStripProps', () => {
  it('retains responseTimeMs when the message has no plan', () => {
    const props = getToolStripProps(makeMessage(), 0);
    expect(props.responseTimeMs).toBe(4200);
  });

  it('suppresses responseTimeMs when a plan is present — its header shows the time instead', () => {
    const withPlan = makeMessage({
      plan: [
        {
          step: 1,
          description: 'Search arXiv',
          tool: 'search_arxiv',
          args_hint: {},
          depends_on: [],
        },
      ],
    });
    const props = getToolStripProps(withPlan, 0);
    expect(props.responseTimeMs).toBeUndefined();
  });

  it('retains responseTimeMs when plan is an empty array', () => {
    const props = getToolStripProps(makeMessage({ plan: [] }), 0);
    expect(props.responseTimeMs).toBe(4200);
  });
});

describe('ToolStrip timing split', () => {
  it('names the wait before the answer started', () => {
    render(<ToolStrip responseTimeMs={25_800} ttftMs={24_100} />);
    expect(screen.getByText('· first word 24.1s')).toBeInTheDocument();
    expect(screen.getByTitle(/24\.1s to the first word/)).toBeInTheDocument();
  });

  it('shows the total alone when the row has no first-token reading', () => {
    // Every assistant row written before chat_messages.ttft_ms existed.
    render(<ToolStrip responseTimeMs={25_800} />);
    expect(screen.queryByText(/first word/)).not.toBeInTheDocument();
    expect(screen.getByText(/25\.8s/)).toBeInTheDocument();
  });

  it('keeps a sub-second wait to the tooltip', () => {
    render(<ToolStrip responseTimeMs={2000} ttftMs={400} />);
    expect(screen.queryByText(/first word/)).not.toBeInTheDocument();
    expect(screen.getByTitle(/0\.4s to the first word/)).toBeInTheDocument();
  });
});
