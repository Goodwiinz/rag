/**
 * Round-3 L16: the citation badge was a button with no click handler, so its
 * source preview was reachable by pointer hover only — never by tap.
 */
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AgentCitationBadge } from '../AgentCitationBadge';

const citation = {
  documentId: 'doc-1',
  documentTitle: 'Attention Is All You Need',
  snippet: 'We propose a new simple network architecture.',
  score: 0.91,
};

describe('AgentCitationBadge', () => {
  it('opens the source preview on click', () => {
    render(<AgentCitationBadge citationNumber={1} citation={citation} />);

    const badge = screen.getByRole('button', { name: /^Citation 1/ });
    expect(badge).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(badge);

    expect(badge).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
  });

  it('opens the source preview on a touch tap', () => {
    // Radix suppresses the compatibility click on touch, so the tap has to be
    // handled from the pointer event.
    render(<AgentCitationBadge citationNumber={1} citation={citation} />);

    const badge = screen.getByRole('button', { name: /^Citation 1/ });
    fireEvent.pointerUp(badge, { pointerType: 'touch' });

    expect(badge).toHaveAttribute('aria-expanded', 'true');
  });

  it('does not double-toggle when a mouse click follows its pointerup', () => {
    render(<AgentCitationBadge citationNumber={1} citation={citation} />);

    const badge = screen.getByRole('button', { name: /^Citation 1/ });
    fireEvent.pointerUp(badge, { pointerType: 'mouse' });
    fireEvent.click(badge, { pointerType: 'mouse' });

    expect(badge).toHaveAttribute('aria-expanded', 'true');
  });

  it('stays inert when the index resolves to no source', () => {
    render(<AgentCitationBadge citationNumber={7} />);

    const badge = screen.getByRole('button', { name: 'Citation 7' });
    expect(badge).not.toHaveAttribute('aria-expanded');
  });
});
