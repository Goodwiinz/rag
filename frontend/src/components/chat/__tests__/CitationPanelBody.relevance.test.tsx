import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { CitationPanelBody } from '../CitationPanelBody';
import type { Citation } from '@/utils/citationParser';

function citation(overrides: Partial<Citation>): Citation {
  return {
    number: 1,
    title: 'Retrieval-Augmented Generation',
    content: 'A passage of retrieved text.',
    score: 0.5,
    source: 'arxiv',
    ...overrides,
  } as Citation;
}

/** The bar's inline `background`, which encodes the relevance tier. */
function fillsFor(container: HTMLElement): string[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>('span.origin-left')
  ).map((el) => el.style.background);
}

describe('CitationPanelBody relevance meter', () => {
  it('tiers the bar fill by score', () => {
    const { container } = render(
      <CitationPanelBody
        citations={[
          citation({ number: 1, title: 'Strong hit', score: 0.92 }),
          citation({ number: 2, title: 'Middling hit', score: 0.61 }),
          citation({ number: 3, title: 'Weak hit', score: 0.22 }),
        ]}
      />
    );

    const fills = fillsFor(container);
    expect(fills).toContain('var(--nous-sol-intense)');
    expect(fills).toContain('var(--nous-sol)');
    expect(fills).toContain('var(--nous-sol-muted)');
  });

  it('renders no meter for synthetic zero-score citations', () => {
    const { container } = render(
      <CitationPanelBody
        citations={[citation({ number: 1, title: 'Preview only', score: 0 })]}
      />
    );

    expect(fillsFor(container)).toHaveLength(0);
    expect(screen.getByText('Preview only')).toBeInTheDocument();
  });
});
