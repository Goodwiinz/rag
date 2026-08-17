/**
 * The inline citation marker's four states.
 *
 * The marker rests quiet and only reaches full contrast when it is the one
 * being read, so "is it visually distinguishable" is the thing worth pinning —
 * a regression here is silent, and a paragraph can carry ten of these.
 */

import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CitationLink } from '../CitationLink';
import type { Citation } from '@/utils/citationParser';

function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    number: 1,
    title: 'Attention Is All You Need',
    content: 'The Transformer follows this overall architecture.',
    score: 0.91,
    source: 'arxiv',
    documentId: 'doc-1',
    ...overrides,
  } as Citation;
}

const marker = (): HTMLElement => screen.getByRole('button', { name: /Citation 1/ });

describe('CitationLink marker', () => {
  it('rests as a low-contrast chip and inverts when active', () => {
    const { rerender } = render(
      <CitationLink citationNumber={1} citation={citation()} />
    );
    // 60% is the lowest step clearing 4.5:1 against the 6% chip in both
    // themes; 45% (the upstream value) measures 3.1:1 in light.
    expect(marker().className).toContain('text-foreground/60');
    expect(marker().className).not.toContain('bg-foreground text-background');

    rerender(<CitationLink citationNumber={1} citation={citation()} isActive />);
    expect(marker().className).toContain('bg-foreground');
    expect(marker().className).toContain('text-background');
  });

  it('marks an external reference as non-navigable', () => {
    render(
      <CitationLink
        citationNumber={1}
        citation={citation({ documentId: undefined, externalReferenceId: '2301.00001' })}
      />
    );
    // Outlined rather than filled, and it does not present as clickable.
    expect(marker().className).toContain('cursor-default');
    expect(marker()).toHaveAccessibleName(/external reference/i);
  });

  it('disables the marker when no citation resolved', () => {
    render(<CitationLink citationNumber={1} />);
    expect(marker()).toBeDisabled();
    expect(marker().className).toContain('cursor-not-allowed');
  });

  it('routes a click to the citation, not the surrounding message', () => {
    const onClick = vi.fn();
    const c = citation();
    render(<CitationLink citationNumber={1} citation={c} onClick={onClick} />);

    fireEvent.click(marker());
    expect(onClick).toHaveBeenCalledWith(c);
  });
});
