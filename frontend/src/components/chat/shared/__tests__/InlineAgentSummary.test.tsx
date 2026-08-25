import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { InlineAgentSummary } from '../InlineAgentSummary';

describe('InlineAgentSummary', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('does not present an unresolved terminal tool as complete', () => {
    act(() => {
      const activity = useAgentActivityStore.getState();
      activity.startRun('thread-1', 'Nous', 'Search');
      activity.pushToolStart('thread-1', 'search_documents', 'call-1');
      activity.finishRun('thread-1', 'done');
    });

    render(<InlineAgentSummary threadId="thread-1" />);
    expect(
      screen.getByText('Used 1 tool · 1 status unavailable')
    ).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: /show agent steps/i }));
    expect(
      screen.getByText('Search documents status unavailable')
    ).toBeVisible();
  });
});
