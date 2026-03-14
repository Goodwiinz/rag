import React from 'react';
import { render } from '../../__tests__/testUtils';
import { expectNoA11yViolations } from '@/test/a11y';
import SearchInterface from '../SearchInterface';

describe('SearchInterface a11y', () => {
  const mockOnSearch = jest.fn().mockResolvedValue(undefined);
  const mockOnGetHistory = jest.fn().mockResolvedValue([]);

  const defaultProps = {
    onSearch: mockOnSearch,
    onGetHistory: mockOnGetHistory,
  };

  beforeEach(() => {
    jest.clearAllMocks();
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
