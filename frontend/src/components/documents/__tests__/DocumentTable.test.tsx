import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentTable } from '../DocumentTable';

// Minimal type mirroring the component's internal Document interface
interface TableDocument {
  id: string;
  name: string;
  type: string;
  status: 'processing' | 'completed' | 'failed';
  size: string;
  uploadedAt: string;
  progress?: number;
}

const makeDocs = (
  overrides: Partial<TableDocument>[] = []
): TableDocument[] => {
  const defaults: TableDocument[] = [
    {
      id: '1',
      name: 'Q4_Financial_Report.pdf',
      type: 'pdf',
      status: 'completed',
      size: '2.4 MB',
      uploadedAt: '2024-01-15',
    },
    {
      id: '2',
      name: 'Product_Demo.mp4',
      type: 'video',
      status: 'processing',
      size: '15.7 MB',
      uploadedAt: '2024-01-16',
      progress: 65,
    },
    {
      id: '3',
      name: 'Meeting_Notes.txt',
      type: 'text',
      status: 'failed',
      size: '24 KB',
      uploadedAt: '2024-01-14',
    },
  ];
  return overrides.length
    ? overrides.map((o, i) => ({ ...defaults[i % defaults.length]!, ...o }))
    : defaults;
};

describe('DocumentTable', () => {
  // ---------------------------------------------------------------
  // Column headers
  // ---------------------------------------------------------------
  it('renders the correct column headers', () => {
    render(<DocumentTable documents={makeDocs()} />);

    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Size')).toBeInTheDocument();
    expect(screen.getByText('Uploaded')).toBeInTheDocument();
    // "Actions" is the column header text
    expect(screen.getAllByText('Actions').length).toBeGreaterThanOrEqual(1);
  });

  // ---------------------------------------------------------------
  // Renders rows for each document
  // ---------------------------------------------------------------
  it('renders a row for every document', () => {
    const docs = makeDocs();
    render(<DocumentTable documents={docs} />);

    for (const doc of docs) {
      expect(screen.getByText(doc.name)).toBeInTheDocument();
    }
  });

  // ---------------------------------------------------------------
  // Document type displayed in uppercase
  // ---------------------------------------------------------------
  it('displays document type in uppercase', () => {
    render(<DocumentTable documents={makeDocs()} />);

    expect(screen.getByText('PDF')).toBeInTheDocument();
    expect(screen.getByText('VIDEO')).toBeInTheDocument();
    expect(screen.getByText('TEXT')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Status badges
  // ---------------------------------------------------------------
  it('renders correct status badges for each state', () => {
    render(<DocumentTable documents={makeDocs()} />);

    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Processing')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Size column
  // ---------------------------------------------------------------
  it('shows file sizes for each document', () => {
    render(<DocumentTable documents={makeDocs()} />);

    expect(screen.getByText('2.4 MB')).toBeInTheDocument();
    expect(screen.getByText('15.7 MB')).toBeInTheDocument();
    expect(screen.getByText('24 KB')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Date column formats dates
  // ---------------------------------------------------------------
  it('formats uploaded dates via toLocaleDateString', () => {
    const docs = makeDocs([
      { id: 'date-1', name: 'DateDoc.pdf', uploadedAt: '2024-06-15' },
    ]);
    render(<DocumentTable documents={docs} />);

    const formatted = new Date('2024-06-15').toLocaleDateString();
    expect(screen.getByText(formatted)).toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Empty state: no rows when documents array is empty
  // ---------------------------------------------------------------
  it('renders an empty table body when no documents are provided', () => {
    render(<DocumentTable documents={[]} />);

    // Headers should still be present
    expect(screen.getByText('Name')).toBeInTheDocument();

    // No document names should be rendered
    expect(
      screen.queryByText('Q4_Financial_Report.pdf')
    ).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Progress bar for processing documents
  // ---------------------------------------------------------------
  it('shows a progress bar for processing documents with progress', () => {
    const docs = makeDocs([
      { id: 'p1', name: 'uploading.pdf', status: 'processing', progress: 45 },
    ]);
    const { container } = render(<DocumentTable documents={docs} />);

    // The progress bar inner div has a width style based on the progress %
    const progressBar = container.querySelector('[style*="width: 45%"]');
    expect(progressBar).toBeInTheDocument();
  });

  it('does not show a progress bar for completed documents', () => {
    const docs = makeDocs([
      { id: 'c1', name: 'done.pdf', status: 'completed', progress: 100 },
    ]);
    const { container } = render(<DocumentTable documents={docs} />);

    // Progress bar should not render for non-processing status
    const progressBar = container.querySelector('[style*="width: 100%"]');
    expect(progressBar).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------
  // Action menu buttons (open menu)
  // ---------------------------------------------------------------
  it('renders an action menu button for each row', () => {
    const docs = makeDocs();
    render(<DocumentTable documents={docs} />);

    const menuButtons = screen.getAllByRole('button', { name: /open menu/i });
    expect(menuButtons).toHaveLength(docs.length);
  });

  // ---------------------------------------------------------------
  // Callback: onView
  // ---------------------------------------------------------------
  it('calls onView when the View menu item is clicked', async () => {
    const user = userEvent.setup();
    const onView = jest.fn();
    const docs = makeDocs([
      { id: 'v1', name: 'viewable.pdf', status: 'completed' },
    ]);

    render(<DocumentTable documents={docs} onView={onView} />);

    // Open the dropdown menu
    const menuBtn = screen.getByRole('button', { name: /open menu/i });
    await user.click(menuBtn);

    // Click the View item
    const viewItem = screen.getByText('View');
    await user.click(viewItem);

    expect(onView).toHaveBeenCalledTimes(1);
    expect(onView).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'v1', name: 'viewable.pdf' })
    );
  });

  // ---------------------------------------------------------------
  // Callback: onDownload
  // ---------------------------------------------------------------
  it('calls onDownload when the Download menu item is clicked', async () => {
    const user = userEvent.setup();
    const onDownload = jest.fn();
    const docs = makeDocs([
      { id: 'd1', name: 'downloadable.pdf', status: 'completed' },
    ]);

    render(<DocumentTable documents={docs} onDownload={onDownload} />);

    const menuBtn = screen.getByRole('button', { name: /open menu/i });
    await user.click(menuBtn);

    const downloadItem = screen.getByText('Download');
    await user.click(downloadItem);

    expect(onDownload).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'd1' })
    );
  });

  // ---------------------------------------------------------------
  // Callback: onDelete
  // ---------------------------------------------------------------
  it('calls onDelete when the Delete menu item is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const docs = makeDocs([
      { id: 'del1', name: 'removable.pdf', status: 'failed' },
    ]);

    render(<DocumentTable documents={docs} onDelete={onDelete} />);

    const menuBtn = screen.getByRole('button', { name: /open menu/i });
    await user.click(menuBtn);

    const deleteItem = screen.getByText('Delete');
    await user.click(deleteItem);

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'del1' })
    );
  });

  // ---------------------------------------------------------------
  // Gracefully handles missing callbacks
  // ---------------------------------------------------------------
  it('does not throw when action callbacks are not provided', async () => {
    const user = userEvent.setup();
    const docs = makeDocs([
      { id: 'no-cb', name: 'safe.pdf', status: 'completed' },
    ]);

    render(<DocumentTable documents={docs} />);

    const menuBtn = screen.getByRole('button', { name: /open menu/i });
    await user.click(menuBtn);

    // Clicking View without an onView handler should not throw
    const viewItem = screen.getByText('View');
    await expect(user.click(viewItem)).resolves.not.toThrow();
  });

  // ---------------------------------------------------------------
  // Single document renders correctly
  // ---------------------------------------------------------------
  it('renders correctly with a single document', () => {
    const docs = makeDocs([
      {
        id: 'only-1',
        name: 'solo.pdf',
        type: 'pdf',
        status: 'completed',
        size: '1 KB',
      },
    ]);
    render(<DocumentTable documents={docs} />);

    expect(screen.getByText('solo.pdf')).toBeInTheDocument();
    expect(screen.getByText('1 KB')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /open menu/i })).toHaveLength(
      1
    );
  });
});
