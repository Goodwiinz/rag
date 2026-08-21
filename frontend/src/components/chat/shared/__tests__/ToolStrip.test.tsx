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

  it('retains responseTimeMs when a plan is present', () => {
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
    expect(props.responseTimeMs).toBe(4200);
  });

  it('retains responseTimeMs when plan is an empty array', () => {
    const props = getToolStripProps(makeMessage({ plan: [] }), 0);
    expect(props.responseTimeMs).toBe(4200);
  });
});

describe('ToolStrip message timing', () => {
  it('uses one assistant-ui MessageTiming for all turn metrics', () => {
    const { container } = render(
      <ToolStrip
        responseTimeMs={25_800}
        ttftMs={24_100}
        tokenUsage={{ input: 4300, output: 195 }}
      />
    );
    expect(
      container.querySelectorAll('[data-slot="message-timing"]')
    ).toHaveLength(1);
    expect(screen.getByText('first word')).toBeInTheDocument();
    expect(screen.getByText('24.1s')).toBeInTheDocument();
    expect(screen.getByText('total')).toBeInTheDocument();
    expect(screen.getByText('25.8s')).toBeInTheDocument();
    expect(screen.getByText('tokens')).toBeInTheDocument();
    expect(screen.getByText('4.3k in · 195 out')).toBeInTheDocument();
  });

  it('omits first-word timing when the row has no first-token reading', () => {
    render(<ToolStrip responseTimeMs={25_800} />);
    expect(screen.queryByText(/first word/)).not.toBeInTheDocument();
    expect(screen.getByText('25.8s')).toBeInTheDocument();
  });
});
