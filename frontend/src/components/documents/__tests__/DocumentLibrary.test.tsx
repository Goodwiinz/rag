import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Document } from '@/types';

// ---------------------------------------------------------------------------
// Mock useDocuments hook
// ---------------------------------------------------------------------------
const mockFetchDocuments = jest.fn();
const mockUpdateFilters = jest.fn();
const mockUpdatePage = jest.fn();
const mockUpdatePageSize = jest.fn();
const mockSelectDocument = jest.fn();
const mockSelectAllDocuments = jest.fn();
const mockClearSelection = jest.fn();
const mockDeleteDocument = jest.fn();
const mockDeleteSelectedDocuments = jest.fn();
const mockRefreshDocuments = jest.fn();
const mockRetryDocument = jest.fn();

const defaultHookReturn = {
  documents: [] as Document[],
  loading: false,
  error: null as string | null,
  pagination: {
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
    hasNext: false,
    hasPrev: false,
  },
  filters: {},
  selectedDocuments: new Set<string>(),
  selectedCount: 0,
  hasSelection: false,
  isAllSelected: false,
  fetchDocuments: mockFetchDocuments,
  updateFilters: mockUpdateFilters,
  updatePage: mockUpdatePage,
  updatePageSize: mockUpdatePageSize,
  selectDocument: mockSelectDocument,
  selectAllDocuments: mockSelectAllDocuments,
  clearSelection: mockClearSelection,
  deleteDocument: mockDeleteDocument,
  deleteSelectedDocuments: mockDeleteSelectedDocuments,
  refreshDocuments: mockRefreshDocuments,
  retryDocument: mockRetryDocument,
};

let hookOverrides: Partial<typeof defaultHookReturn> = {};

jest.mock('@/hooks/useDocuments', () => ({
  useDocuments: () => ({ ...defaultHookReturn, ...hookOverrides }),
}));

// ---------------------------------------------------------------------------
// Mock authStore
// ---------------------------------------------------------------------------
let mockIsAuthenticated = true;

jest.mock('@/store/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

// ---------------------------------------------------------------------------
// Mock DocumentCard to keep tests focused on DocumentLibrary logic
// ---------------------------------------------------------------------------
jest.mock('../DocumentCard', () => ({
  DocumentCard: ({
    document,
    selected,
    onSelect,
    onPreview,
    onDelete,
    onRetry,
  }: {
    document: Document;
    selected: boolean;
    onSelect: (id: string) => void;
    onPreview: (doc: Document) => void;
    onDelete: (id: string) => void;
    onRetry: (id: string) => void;
  }) => (
    <div data-testid={`doc-card-${document.id}`}>
      <span>{document.title}</span>
      {selected && <span data-testid="selected-badge">selected</span>}
      <button onClick={() => onSelect(document.id)}>Select</button>
      <button onClick={() => onPreview(document)}>Preview</button>
      <button onClick={() => onDelete(document.id)}>Delete</button>
      <button onClick={() => onRetry(document.id)}>Retry</button>
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const makeDocument = (overrides: Partial<Document> = {}): Document => ({
  id: 'doc-1',
  user_id: 'user-1',
  organization_id: 'org-1',
  title: 'Test Document',
  filename: 'test.pdf',
  file_type: 'pdf',
  file_size: 1024,
  processing_status: 'indexed',
  upload_timestamp: '2024-01-15T00:00:00Z',
  metadata: {},
  ...overrides,
});

import { DocumentLibrary } from '../DocumentLibrary';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('DocumentLibrary', () => {
  beforeEach(() => {
    hookOverrides = {};
    mockIsAuthenticated = true;
  });

  // ---------------------------------------------------------------
  // Renders header and document count
  // ---------------------------------------------------------------
  it('renders the heading and document count', () => {
    hookOverrides = {
      pagination: { ...defaultHookReturn.pagination, total: 5 },
    };
    render(<DocumentLibrary />);

    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('5 documents')).toBeInTheDocument();
  });

  it('uses singular "document" when total is 1', () => {
    hookOverrides = {
      pagination: { ...defaultHookReturn.pagination, total: 1 },
    };
    render(<DocumentLibrary />);

    expect(screen.getByText('1 document')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------
  it('shows loading skeleton placeholders while loading', () => {
    hookOverrides = { loading: true };
    const { container } = render(<DocumentLibrary />);

    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThanOrEqual(1);
  });

  it('does not show documents while loading', () => {
    hookOverrides = {
      loading: true,
      documents: [makeDocument()],
    };
    render(<DocumentLibrary />);

    // DocumentCard mocks render the title; they should not appear during loading
    expect(screen.queryByText('Test Document')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------
  it('displays error message and Try Again button on error', () => {
    hookOverrides = { error: 'Network request failed' };
    render(<DocumentLibrary />);

    expect(screen.getByText('Network request failed')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /try again/i })
    ).toBeInTheDocument();
  });

  it('calls refreshDocuments when Try Again is clicked', async () => {
    const user = userEvent.setup();
    hookOverrides = { error: 'Server error' };
    render(<DocumentLibrary />);

    await user.click(screen.getByRole('button', { name: /try again/i }));
    expect(mockRefreshDocuments).toHaveBeenCalledTimes(1);
  });

  // ---------------------------------------------------------------
  // Empty state (authenticated)
  // ---------------------------------------------------------------
  it('shows "No documents found" when there are no documents', () => {
    hookOverrides = { documents: [] };
    render(<DocumentLibrary />);

    expect(screen.getByText('No documents found')).toBeInTheDocument();
    expect(
      screen.getByText('Upload your first document to get started')
    ).toBeInTheDocument();
  });

  it('shows filter hint when filters are active and no documents match', () => {
    hookOverrides = {
      documents: [],
      filters: { search_term: 'nonexistent' },
    };
    render(<DocumentLibrary />);

    expect(
      screen.getByText('Try adjusting your filters or search terms')
    ).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Empty state (not authenticated)
  // ---------------------------------------------------------------
  it('shows login prompt when not authenticated', () => {
    mockIsAuthenticated = false;
    hookOverrides = { documents: [] };
    render(<DocumentLibrary />);

    expect(screen.getByText('Please log in')).toBeInTheDocument();
    expect(
      screen.getByText('You need to log in to view and upload documents')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /go to login/i })
    ).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Documents render via DocumentCard
  // ---------------------------------------------------------------
  it('renders DocumentCards for each document', () => {
    const docs = [
      makeDocument({ id: 'a', title: 'Alpha Doc' }),
      makeDocument({ id: 'b', title: 'Beta Doc' }),
      makeDocument({ id: 'c', title: 'Gamma Doc' }),
    ];
    hookOverrides = {
      documents: docs,
      pagination: { ...defaultHookReturn.pagination, total: 3 },
    };
    render(<DocumentLibrary />);

    expect(screen.getByText('Alpha Doc')).toBeInTheDocument();
    expect(screen.getByText('Beta Doc')).toBeInTheDocument();
    expect(screen.getByText('Gamma Doc')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Search input
  // ---------------------------------------------------------------
  it('renders a search input', () => {
    render(<DocumentLibrary />);

    expect(
      screen.getByPlaceholderText('Search documents...')
    ).toBeInTheDocument();
  });

  it('calls updateFilters when typing in the search input', async () => {
    const user = userEvent.setup();
    render(<DocumentLibrary />);

    const searchInput = screen.getByPlaceholderText('Search documents...');
    await user.type(searchInput, 'report');

    // updateFilters should have been called for each keystroke
    expect(mockUpdateFilters).toHaveBeenCalled();
    // The last call should include the full typed string
    const lastCall =
      mockUpdateFilters.mock.calls[mockUpdateFilters.mock.calls.length - 1];
    expect(lastCall[0]).toEqual({ search_term: 'report' });
  });

  // ---------------------------------------------------------------
  // Refresh button
  // ---------------------------------------------------------------
  it('calls refreshDocuments when clicking Refresh', async () => {
    const user = userEvent.setup();
    render(<DocumentLibrary />);

    await user.click(screen.getByRole('button', { name: /refresh/i }));
    expect(mockRefreshDocuments).toHaveBeenCalledTimes(1);
  });

  it('disables Refresh button while loading', () => {
    hookOverrides = { loading: true };
    render(<DocumentLibrary />);

    expect(screen.getByRole('button', { name: /refresh/i })).toBeDisabled();
  });

  // ---------------------------------------------------------------
  // Bulk selection bar
  // ---------------------------------------------------------------
  it('shows bulk action bar when documents are selected', () => {
    hookOverrides = {
      documents: [makeDocument()],
      hasSelection: true,
      selectedCount: 2,
      selectedDocuments: new Set(['doc-1', 'doc-2']),
    };
    render(<DocumentLibrary />);

    expect(screen.getByText('2 selected')).toBeInTheDocument();
    expect(screen.getByText('Clear selection')).toBeInTheDocument();
  });

  it('does not show bulk action bar when no documents are selected', () => {
    hookOverrides = {
      documents: [makeDocument()],
      hasSelection: false,
      selectedCount: 0,
    };
    render(<DocumentLibrary />);

    expect(screen.queryByText('Clear selection')).not.toBeInTheDocument();
  });

  it('calls clearSelection when Clear selection is clicked', async () => {
    const user = userEvent.setup();
    hookOverrides = {
      documents: [makeDocument()],
      hasSelection: true,
      selectedCount: 1,
      selectedDocuments: new Set(['doc-1']),
    };
    render(<DocumentLibrary />);

    await user.click(screen.getByText('Clear selection'));
    expect(mockClearSelection).toHaveBeenCalledTimes(1);
  });

  // ---------------------------------------------------------------
  // Pagination info
  // ---------------------------------------------------------------
  it('shows pagination info when documents are present', () => {
    hookOverrides = {
      documents: [makeDocument()],
      pagination: {
        page: 1,
        pageSize: 20,
        total: 50,
        totalPages: 3,
        hasNext: true,
        hasPrev: false,
      },
    };
    render(<DocumentLibrary />);

    expect(
      screen.getByText(/Showing 1 to 20 of 50 documents/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // className prop is forwarded
  // ---------------------------------------------------------------
  it('applies custom className', () => {
    const { container } = render(
      <DocumentLibrary className="my-custom-class" />
    );

    expect(container.firstElementChild).toHaveClass('my-custom-class');
  });

  // ---------------------------------------------------------------
  // Renders without crashing with minimal props
  // ---------------------------------------------------------------
  it('renders without crashing with no props', () => {
    const { container } = render(<DocumentLibrary />);
    expect(container).toBeTruthy();
  });
});
