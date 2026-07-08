import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AllCitationsPanel } from '../AllCitationsPanel';

describe('AllCitationsPanel', () => {
  it('renders nothing when no citations (Cowork-style — hide empty cards)', () => {
    const { container } = render(<AllCitationsPanel allCitations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders title and source for each citation with source count', () => {
    render(
      <AllCitationsPanel
        allCitations={[
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
        ]}
      />
    );
    expect(screen.getByText('Internal doc')).toBeTruthy();
    expect(screen.getByText('External paper')).toBeTruthy();
    expect(screen.getByText(/2 sources/i)).toBeTruthy();
  });

  it('renders singular "source" when count is 1', () => {
    render(
      <AllCitationsPanel
        allCitations={[{ documentId: 'd1', title: 'Lonely doc', score: 0.9 }]}
      />
    );
    expect(screen.getByText(/1 source$/i)).toBeTruthy();
  });
});
