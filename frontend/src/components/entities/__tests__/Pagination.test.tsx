import React from 'react';
import { render, screen } from '@testing-library/react';
import { Pagination } from '../Pagination';

// Mock icons to prevent issues with lucide-react in jest environment
jest.mock('lucide-react', () => ({
  ChevronLeft: () => <svg data-testid="chevron-left" />,
  ChevronRight: () => <svg data-testid="chevron-right" />,
  ChevronsLeft: () => <svg data-testid="chevrons-left" />,
  ChevronsRight: () => <svg data-testid="chevrons-right" />,
  ChevronDown: () => <svg data-testid="chevron-down" />,
  Check: () => <svg data-testid="check" />,
}));

// Mock Select components to avoid Radix UI issues in test environment (React version conflict)
jest.mock('@/components/ui/select', () => ({
  Select: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectTrigger: ({ children, 'aria-labelledby': ariaLabelledBy }: any) => (
    <button aria-labelledby={ariaLabelledBy}>{children}</button>
  ),
  SelectValue: () => <span>Select Value</span>,
  SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe('Pagination Component', () => {
  const defaultProps = {
    currentPage: 2,
    totalPages: 5,
    pageSize: 25,
    totalItems: 125,
    onPageChange: jest.fn(),
    onPageSizeChange: jest.fn(),
  };

  it('renders correctly with accessibility attributes', () => {
    render(<Pagination {...defaultProps} />);

    // Check for "Rows per page" label association
    const rowsLabel = screen.getByText('Rows:');
    expect(rowsLabel).toBeInTheDocument();
    // Verify the label has the id used by aria-labelledby
    expect(rowsLabel).toHaveAttribute('id', 'rows-per-page-label');

    // Check navigation buttons accessibility
    const firstPageBtn = screen.getByLabelText('Go to first page');
    const prevPageBtn = screen.getByLabelText('Go to previous page');
    const nextPageBtn = screen.getByLabelText('Go to next page');
    const lastPageBtn = screen.getByLabelText('Go to last page');

    expect(firstPageBtn).toBeInTheDocument();
    expect(prevPageBtn).toBeInTheDocument();
    expect(nextPageBtn).toBeInTheDocument();
    expect(lastPageBtn).toBeInTheDocument();

    // Check page number buttons accessibility
    const page1Btn = screen.getByLabelText('Page 1');
    const page2Btn = screen.getByLabelText('Page 2');

    expect(page1Btn).toBeInTheDocument();
    expect(page2Btn).toBeInTheDocument();

    // Check aria-current on active page
    expect(page2Btn).toHaveAttribute('aria-current', 'page');
    expect(page1Btn).not.toHaveAttribute('aria-current');
  });

  it('buttons are disabled appropriately', () => {
    render(<Pagination {...defaultProps} currentPage={1} />);

    const firstPageBtn = screen.getByLabelText('Go to first page');
    const prevPageBtn = screen.getByLabelText('Go to previous page');

    expect(firstPageBtn).toBeDisabled();
    expect(prevPageBtn).toBeDisabled();
  });
});
