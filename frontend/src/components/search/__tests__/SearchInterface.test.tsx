import React from 'react';
import { render, screen, fireEvent } from '../../__tests__/testUtils';
import SearchInterface from '../SearchInterface';

describe('SearchInterface', () => {
  const mockOnSearch = jest.fn();
  const mockOnGetSuggestions = jest.fn();
  const mockOnGetHistory = jest.fn().mockResolvedValue([]);
  const mockOnSaveSearch = jest.fn();

  const defaultProps = {
    onSearch: mockOnSearch,
    onGetSuggestions: mockOnGetSuggestions,
    onGetHistory: mockOnGetHistory,
    onSaveSearch: mockOnSaveSearch,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders correctly', () => {
    render(<SearchInterface {...defaultProps} />);
    expect(
      screen.getByPlaceholderText('Search your documents...')
    ).toBeInTheDocument();
  });

  it('shows clear button when text is entered and clears input when clicked', () => {
    render(<SearchInterface {...defaultProps} />);
    const input = screen.getByPlaceholderText('Search your documents...');

    // Initially clear button should not be visible
    expect(
      screen.queryByLabelText('Clear search')
    ).not.toBeInTheDocument();

    // Type text
    fireEvent.change(input, { target: { value: 'test query' } });

    // Clear button should be visible
    const clearButton = screen.getByLabelText('Clear search');
    expect(clearButton).toBeInTheDocument();

    // Click clear button
    fireEvent.click(clearButton);

    // Input should be empty
    expect(input).toHaveValue('');

    // Input should be focused
    expect(input).toHaveFocus();

    // Clear button should be gone
    expect(
      screen.queryByLabelText('Clear search')
    ).not.toBeInTheDocument();
  });

  it('has accessible labels for buttons and inputs', () => {
    render(<SearchInterface {...defaultProps} />);

    expect(screen.getByLabelText('Search query')).toBeInTheDocument();
    expect(screen.getByLabelText('Toggle filters')).toBeInTheDocument();
    expect(screen.getByLabelText('Search')).toBeInTheDocument();
  });
});
