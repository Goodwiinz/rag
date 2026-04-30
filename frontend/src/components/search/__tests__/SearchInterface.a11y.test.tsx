import { beforeEach, describe, it, vi } from 'vitest';
import React from 'react';
import { render } from '@/test/test-utils';
import { expectNoA11yViolations } from '@/test/a11y';
import SearchInterface from '../SearchInterface';

describe('SearchInterface a11y', () => {
  const mockOnSearch = vi.fn().mockResolvedValue(undefined);
  const mockOnGetHistory = vi.fn().mockResolvedValue([]);

  const defaultProps = {
    onSearch: mockOnSearch,
    onGetHistory: mockOnGetHistory,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<SearchInterface {...defaultProps} />);
    await expectNoA11yViolations(container);
  });

  it('has no accessibility violations when loading', async () => {
    const { container } = render(
      <SearchInterface {...defaultProps} loading={true} />
    );
    await expectNoA11yViolations(container);
  });
});
