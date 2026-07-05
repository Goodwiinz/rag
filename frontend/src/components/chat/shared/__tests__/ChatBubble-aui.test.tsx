import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatBubble } from '../ChatBubble';
import type { ActivityStep } from '../cloudMessageView';

vi.mock('@/components/chat/aui/flag', () => ({ AUI_TOOL_UI_ENABLED: true }));

vi.mock('../../CitationRenderer', () => ({
  CitationRenderer: ({ content }: { content: string }) => <p>{content}</p>,
}));

const toolExecutions: ActivityStep[] = [
  { tool: 'search_arxiv', label: 'Searching arXiv', status: 'done' },
];

describe('ChatBubble with AUI tool UI flag ON', () => {
  it('renders AuiToolParts instead of ChatActivityStrip', () => {
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

    expect(
      document.querySelector('[data-slot="aui-tool-parts"]')
    ).toBeTruthy();
    // ChatActivityStrip's collapsible trigger is labeled "Agent activity — …"
    expect(screen.queryByText(/Agent activity/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /agent activity/i })
    ).not.toBeInTheDocument();
  });
});
