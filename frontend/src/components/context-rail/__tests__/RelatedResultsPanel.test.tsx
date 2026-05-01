/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { RelatedResultsPanel } from '../RelatedResultsPanel';

vi.mock('@/hooks', () => ({
  useCitationsForThread: vi.fn(),
}));

const { useCitationsForThread } = require('@/hooks');

describe('RelatedResultsPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when no related results (Cowork-style — hide empty cards)', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [],
    });
    const { container } = render(<RelatedResultsPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders populated list with titles and scores', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [
        { documentId: 'd1', title: 'Paper A', score: 0.82, source: 'arxiv' },
        { documentId: 'd2', title: 'Paper B', score: 0.55, source: 'upload' },
      ],
    });
    render(<RelatedResultsPanel />);
    expect(screen.getByText('Paper A')).toBeTruthy();
    expect(screen.getByText('Paper B')).toBeTruthy();
    expect(screen.getByText('82% match')).toBeTruthy();
    expect(screen.getByText('55% match')).toBeTruthy();
  });
});
