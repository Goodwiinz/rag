import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DocumentStats } from '../../../../app/(dashboard)/documents/components/DocumentStats';

describe('DocumentStats', () => {
  it('labels global totals separately from current-page status counts', () => {
    render(
      <DocumentStats
        stats={{
          total: 42,
          visible_indexed: 3,
          visible_processing: 2,
          visible_queued: 4,
          visible_failed: 1,
        }}
      />
    );

    expect(screen.getByText('Total (all matches)')).toBeInTheDocument();
    expect(screen.getByText('Indexed (page)')).toBeInTheDocument();
    expect(screen.getByText('Processing (page)')).toBeInTheDocument();
    expect(screen.getByText('Queued (page)')).toBeInTheDocument();
    expect(screen.getByText('Failed (page)')).toBeInTheDocument();
  });
});
