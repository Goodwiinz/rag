import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { RelatedResultsPanel } from '../RelatedResultsPanel';

describe('RelatedResultsPanel', () => {
  it('renders nothing when no related results (Cowork-style — hide empty cards)', () => {
    const { container } = render(<RelatedResultsPanel relatedResults={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders populated list with titles and scores', () => {
    render(
      <RelatedResultsPanel
        relatedResults={[
          { documentId: 'd1', title: 'Paper A', score: 0.82, source: 'arxiv' },
          { documentId: 'd2', title: 'Paper B', score: 0.55, source: 'upload' },
        ]}
      />
    );
    expect(screen.getByText('Paper A')).toBeTruthy();
    expect(screen.getByText('Paper B')).toBeTruthy();
    expect(screen.getByText('82% match')).toBeTruthy();
    expect(screen.getByText('55% match')).toBeTruthy();
  });
});
