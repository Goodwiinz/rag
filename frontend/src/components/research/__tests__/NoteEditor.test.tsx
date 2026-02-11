import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { NoteEditor } from '@/components/research/NoteEditor';
import type { ProjectDocument, ProjectNote } from '@/services/projectService';

jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

jest.mock('remark-gfm', () => ({
  __esModule: true,
  default: jest.fn(),
}));

const mockNote: ProjectNote = {
  id: 'note-1',
  project_id: 'project-1',
  user_id: 'user-1',
  title: 'Initial Title',
  content: '# Findings\n\nImportant point',
  tags: ['methodology'],
  linked_document_ids: ['doc-1'],
  is_pinned: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const mockDocuments: ProjectDocument[] = [
  {
    id: 'pd-1',
    project_id: 'project-1',
    document_id: 'doc-1',
    added_at: '2026-01-01T00:00:00Z',
    document: {
      id: 'doc-1',
      title: 'Paper One',
      filename: 'paper-one.pdf',
      status: 'processed',
      created_at: '2026-01-01T00:00:00Z',
    },
  },
  {
    id: 'pd-2',
    project_id: 'project-1',
    document_id: 'doc-2',
    added_at: '2026-01-01T00:00:00Z',
    document: {
      id: 'doc-2',
      title: 'Paper Two',
      filename: 'paper-two.pdf',
      status: 'processed',
      created_at: '2026-01-01T00:00:00Z',
    },
  },
];

describe('NoteEditor', () => {
  it('renders initial note fields when editing', () => {
    render(
      <NoteEditor
        isOpen
        initialNote={mockNote}
        availableDocuments={mockDocuments}
        onClose={jest.fn()}
        onSave={jest.fn().mockResolvedValue(undefined)}
      />
    );

    expect(screen.getByDisplayValue('Initial Title')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Write note content in markdown...')).toHaveValue(
      '# Findings\n\nImportant point'
    );
    expect(screen.getByText('Paper One')).toBeInTheDocument();
  });

  it('toggles markdown preview', () => {
    render(
      <NoteEditor
        isOpen
        initialNote={mockNote}
        availableDocuments={mockDocuments}
        onClose={jest.fn()}
        onSave={jest.fn().mockResolvedValue(undefined)}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(screen.getByText(/# Findings/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByPlaceholderText('Write note content in markdown...')).toHaveValue(
      '# Findings\n\nImportant point'
    );
  });

  it('submits updated note payload with tags and linked docs', async () => {
    const onSave = jest.fn().mockResolvedValue(undefined);
    const onClose = jest.fn();

    render(
      <NoteEditor
        isOpen
        initialNote={mockNote}
        availableDocuments={mockDocuments}
        onClose={onClose}
        onSave={onSave}
      />
    );

    fireEvent.change(screen.getByDisplayValue('Initial Title'), {
      target: { value: 'Updated Title' },
    });

    fireEvent.change(screen.getByPlaceholderText('Add tag and press Enter'), {
      target: { value: 'results' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^add$/i }));

    fireEvent.click(screen.getByLabelText('Paper Two'));
    fireEvent.click(screen.getByRole('button', { name: /save note/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Updated Title',
          tags: expect.arrayContaining(['methodology', 'results']),
          linked_document_ids: expect.arrayContaining(['doc-1', 'doc-2']),
        })
      );
      expect(onClose).toHaveBeenCalled();
    });
  });
});
