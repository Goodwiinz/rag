import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ChatInlinePlan } from '../ChatInlinePlan';
import type { PlanStep } from '@/types/agent-chat';

const plan: PlanStep[] = [
  {
    step: 1,
    description: 'Search arXiv for the paper',
    tool: 'search_arxiv',
    args_hint: {},
    depends_on: [],
  },
];

describe('ChatInlinePlan', () => {
  it('defaults collapsed for a committed (non-streaming) instance', () => {
    render(<ChatInlinePlan plan={plan} />);

    expect(screen.getByText('Execution plan')).toBeInTheDocument();
    expect(screen.queryByText('Search arXiv for the paper')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Toggle execution plan' })
    ).toHaveAttribute('aria-expanded', 'false');
  });

  it('defaults open for a streaming instance so steps stream in visibly', () => {
    render(<ChatInlinePlan plan={plan} streaming />);

    expect(screen.getByText('Search arXiv for the paper')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Toggle execution plan' })
    ).toHaveAttribute('aria-expanded', 'true');
  });

  it('shows the elapsed "took …" duration once resting, not while streaming', () => {
    const { rerender } = render(
      <ChatInlinePlan plan={plan} elapsedMs={15_400} />
    );
    expect(screen.getByText('took 15s')).toBeInTheDocument();

    rerender(<ChatInlinePlan plan={plan} streaming elapsedMs={15_400} />);
    expect(screen.queryByText(/took/)).not.toBeInTheDocument();
  });

  it('omits the "took …" duration when elapsed time is unknown or sub-second', () => {
    render(<ChatInlinePlan plan={plan} />);
    expect(screen.queryByText(/took/)).not.toBeInTheDocument();
  });

  it('toggles aria-expanded and visible content on click', () => {
    render(<ChatInlinePlan plan={plan} />);
    const button = screen.getByRole('button', { name: 'Toggle execution plan' });

    expect(button).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Search arXiv for the paper')).toBeInTheDocument();
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });
});
