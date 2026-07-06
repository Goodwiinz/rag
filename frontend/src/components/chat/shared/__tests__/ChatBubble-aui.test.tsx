import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { ChatBubble } from '../ChatBubble';
import type { ActivityStep } from '../cloudMessageView';

vi.mock('../../CitationRenderer', () => ({
  CitationRenderer: ({ content }: { content: string }) => <p>{content}</p>,
}));

const toolExecutions: ActivityStep[] = [
  { tool: 'search_arxiv', label: 'Searching arXiv', status: 'done' },
];

describe('ChatBubble tool-call rendering', () => {
  it('renders AuiToolParts for tool executions', () => {
    render(
      <ChatBubble
        message={{
          id: 'msg-1',
          role: 'assistant',
          content: 'Found two papers.',
          timestamp: Date.now(),
          toolExecutions,
        }}
        index={0}
      />
    );

    expect(document.querySelector('[data-slot="aui-tool-parts"]')).toBeTruthy();
  });
});
