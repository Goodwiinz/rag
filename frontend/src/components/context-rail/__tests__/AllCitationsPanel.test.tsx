/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AllCitationsPanel } from '../AllCitationsPanel';

jest.mock('@/hooks', () => ({
  useCitationsForThread: jest.fn(),
}));

const { useCitationsForThread } = require('@/hooks');

describe('AllCitationsPanel', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders empty state when no citations', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText(/no citations yet/i)).toBeTruthy();
  });

  it('renders title and source for each citation with source count', () => {
    useCitationsForThread.mockReturnValue({
      allCitations: [
        { documentId: 'd1', title: 'Internal doc', score: 0.9, source: 'upload' },
        { externalReferenceId: 'e1', title: 'External paper', score: 0.6, source: 'arxiv' },
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
    useCitationsForThread.mockReturnValue({
      allCitations: [
        { documentId: 'd1', title: 'Lonely doc', score: 0.9 },
      ],
      activeDocument: null,
      relatedResults: [],
    });
    render(<AllCitationsPanel />);
    expect(screen.getByText(/1 source$/i)).toBeTruthy();
  });
});
