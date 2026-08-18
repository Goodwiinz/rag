import { describe, expect, it } from 'vitest';
import { getToolStripProps } from '../ToolStrip';
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
