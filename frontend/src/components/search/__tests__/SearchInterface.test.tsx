/**
 * Unit tests for SearchInterface component
 */

import React from 'react';
import { fireEvent, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SearchInterface from '../SearchInterface';
import { render, createMockSearchResult, mockFetchResponse, createMockApiResponse } from '../../__tests__/testUtils';

// Mock the API calls
const mockSearch = jest.fn();
const mockGetSearchHistory = jest.fn();
const mockGetSearchSuggestions = jest.fn();
const mockSaveSearch = jest.fn();

jest.mock('../../services/apiService', () => ({
  search: mockSearch,
  getSearchHistory: mockGetSearchHistory,
  getSearchSuggestions: mockGetSearchSuggestions,
  saveSearch: mockSaveSearch
}));

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate
}));

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn()
  },
  Toaster: () => null
}));

describe('SearchInterface', () => {
  const defaultProps = {
    onSearch: jest.fn(),
    placeholder: 'Search documents...',
    showHistory: true,
    showSuggestions: true,
    maxSuggestions: 10
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Setup default successful API responses
    mockSearch.mockResolvedValue(createMockApiResponse({
      results: [
        createMockSearchResult({ id: 'result-1', content: 'Test result 1' }),
        createMockSearchResult({ id: 'result-2', content: 'Test result 2' })
      ],
      total: 2,
      query: 'test query'
    }));
    mockGetSearchHistory.mockResolvedValue(createMockApiResponse([
      { id: 'hist-1', query: 'previous search 1', timestamp: '2025-01-17T10:30:00Z' },
      { id: 'hist-2', query: 'previous search 2', timestamp: '2025-01-16T15:45:00Z' }
    ]));
    mockGetSearchSuggestions.mockResolvedValue(createMockApiResponse([
      'suggestion 1',
      'suggestion 2',
      'suggestion 3'
    ]));
  });

  it('renders without crashing', () => {
    render(<SearchInterface {...defaultProps} />);

    expect(screen.getByPlaceholderText(/search documents/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('handles search input', async () => {
    const user = userEvent.setup();
    const onSearch = jest.fn();
    render(<SearchInterface {...defaultProps} onSearch={onSearch} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      await user.type(searchInput, 'test query');
    });

    expect(searchInput).toHaveValue('test query');
  });

  it('submits search on button click', async () => {
    const user = userEvent.setup();
    const onSearch = jest.fn();
    render(<SearchInterface {...defaultProps} onSearch={onSearch} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);
    const searchButton = screen.getByRole('button', { name: /search/i });

    await act(async () => {
      await user.type(searchInput, 'test query');
    });

    await act(async () => {
      await user.click(searchButton);
    });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('test query', {
        filters: {},
        limit: 10,
        offset: 0
      });
    });
  });

  it('submits search on Enter key', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      await user.type(searchInput, 'test query{enter}');
    });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('test query', {
        filters: {},
        limit: 10,
        offset: 0
      });
    });
  });

  it('shows search results', async () => {
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText('Test result 1')).toBeInTheDocument();
      expect(screen.getByText('Test result 2')).toBeInTheDocument();
    });
  });

  it('shows search suggestions while typing', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      await user.type(searchInput, 'test');
    });

    await waitFor(() => {
      expect(screen.getByText('suggestion 1')).toBeInTheDocument();
      expect(screen.getByText('suggestion 2')).toBeInTheDocument();
      expect(screen.getByText('suggestion 3')).toBeInTheDocument();
    });
  });

  it('selects search suggestion on click', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      await user.type(searchInput, 'test');
    });

    await waitFor(() => {
      expect(screen.getByText('suggestion 1')).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByText('suggestion 1'));
    });

    expect(searchInput).toHaveValue('suggestion 1');
    expect(mockSearch).toHaveBeenCalledWith('suggestion 1', expect.any(Object));
  });

  it('shows search history', async () => {
    render(<SearchInterface {...defaultProps} showHistory={true} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.focus(searchInput);
    });

    await waitFor(() => {
      expect(screen.getByText('previous search 1')).toBeInTheDocument();
      expect(screen.getByText('previous search 2')).toBeInTheDocument();
    });
  });

  it('selects history item on click', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} showHistory={true} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.focus(searchInput);
    });

    await waitFor(() => {
      expect(screen.getByText('previous search 1')).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByText('previous search 1'));
    });

    expect(searchInput).toHaveValue('previous search 1');
    expect(mockSearch).toHaveBeenCalledWith('previous search 1', expect.any(Object));
  });

  it('applies search filters', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    // Open filters
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /filters/i }));
    });

    // Set file type filter
    await act(async () => {
      const fileTypeSelect = screen.getByLabelText(/file type/i);
      await user.selectOptions(fileTypeSelect, 'pdf');
    });

    // Set date range filter
    await act(async () => {
      const fromDateInput = screen.getByLabelText(/from date/i);
      await user.type(fromDateInput, '2025-01-01');
    });

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      await user.type(searchInput, 'test query{enter}');
    });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('test query', {
        filters: {
          fileType: 'pdf',
          dateRange: { from: '2025-01-01' }
        },
        limit: 10,
        offset: 0
      });
    });
  });

  it('shows loading state during search', async () => {
    render(<SearchInterface {...defaultProps} />);

    // Mock slow search
    mockSearch.mockImplementation(() => new Promise(resolve =>
      setTimeout(() => resolve(createMockApiResponse({
        results: [createMockSearchResult()],
        total: 1
      })), 1000)
    ));

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText(/searching.../i)).toBeInTheDocument();
    });
  });

  it('shows empty state for no results', async () => {
    mockSearch.mockResolvedValue(createMockApiResponse({
      results: [],
      total: 0,
      query: 'no results query'
    }));

    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'no results query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText(/no results found/i)).toBeInTheDocument();
    });
  });

  it('shows error state for search failure', async () => {
    mockSearch.mockRejectedValue(new Error('Search failed'));

    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'error query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText(/search failed/i)).toBeInTheDocument();
    });
  });

  it('handles pagination', async () => {
    mockSearch.mockResolvedValue(createMockApiResponse({
      results: Array(10).fill(null).map((_, i) => createMockSearchResult({ id: `result-${i}` })),
      total: 25,
      query: 'test query'
    }));

    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText(/showing 1-10 of 25 results/i)).toBeInTheDocument();
    });

    // Click next page
    await act(async () => {
      await userEvent.click(screen.getByRole('button', { name: /next page/i }));
    });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('test query', {
        filters: {},
        limit: 10,
        offset: 10
      });
    });
  });

  it('saves search to history', async () => {
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(mockSaveSearch).toHaveBeenCalledWith('test query', {
        filters: {},
        timestamp: expect.any(String)
      });
    });
  });

  it('clears search input', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);
    const clearButton = screen.getByRole('button', { name: /clear/i });

    await act(async () => {
      await user.type(searchInput, 'test query');
    });

    expect(searchInput).toHaveValue('test query');

    await act(async () => {
      await user.click(clearButton);
    });

    expect(searchInput).toHaveValue('');
  });

  it('shows result details on click', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText('Test result 1')).toBeInTheDocument();
    });

    await act(async () => {
      await user.click(screen.getByText('Test result 1'));
    });

    // Should show result details in a modal or expanded view
    expect(screen.getByText(/result details/i)).toBeInTheDocument();
  });

  it('exports search results', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText('Test result 1')).toBeInTheDocument();
    });

    // Mock download
    const mockCreateObjectURL = jest.fn(() => 'blob:url');
    const mockRevokeObjectURL = jest.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    const mockLink = {
      click: jest.fn(),
      href: '',
      download: ''
    };

    global.HTMLAnchorElement.prototype.click = jest.fn();

    await act(async () => {
      await user.click(screen.getByRole('button', { name: /export/i }));
    });

    // Should trigger download
    expect(mockCreateObjectURL).toHaveBeenCalled();
  });

  it('handles keyboard navigation in results', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'test query' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', code: 'Enter' });
    });

    await waitFor(() => {
      expect(screen.getByText('Test result 1')).toBeInTheDocument();
    });

    // Navigate results with arrow keys
    await act(async () => {
      searchInput.focus();
      await user.keyboard('{ArrowDown}');
    });

    // Should highlight first result
    expect(screen.getByRole('button', { name: /test result 1/i })).toHaveFocus();
  });

  it('debounces search suggestions', async () => {
    const user = userEvent.setup();
    render(<SearchInterface {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/search documents/i);

    // Type quickly - should only make one API call
    await act(async () => {
      await user.type(searchInput, 'test');
      await user.type(searchInput, ' query');
    });

    // Should only call once due to debouncing
    expect(mockGetSearchSuggestions).toHaveBeenCalledTimes(1);
  });
});