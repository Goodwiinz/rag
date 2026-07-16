import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AllCitationsPanel } from '../AllCitationsPanel';
import { useCitationsForThread } from '@/hooks';

vi.mock('@/hooks', () => ({
  useCitationsForThread: vi.fn(),
}));

const mockedUseCitationsForThread = vi.mocked(useCitationsForThread);

describe('AllCitationsPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when no citations (Cowork-style — hide empty cards)', () => {
    mockedUseCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [],
    });
    const { container } = render(<AllCitationsPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders title and source for each citation with source count', () => {
    mockedUseCitationsForThread.mockReturnValue({
      allCitations: [
        {
          documentId: 'd1',
          title: 'Internal doc',
          score: 0.9,
          source: 'upload',
        },
        {
          externalReferenceId: 'e1',
          title: 'External paper',
          score: 0.6,
          source: 'arxiv',
        },
      ],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText('Internal doc')).toBeTruthy();
    expect(screen.getByText('External paper')).toBeTruthy();
    expect(screen.getByText(/2 sources/i)).toBeTruthy();
  });

  it('renders singular "source" when count is 1', () => {
    mockedUseCitationsForThread.mockReturnValue({
      allCitations: [{ documentId: 'd1', title: 'Lonely doc', score: 0.9 }],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText(/1 source$/i)).toBeTruthy();
  });
});
