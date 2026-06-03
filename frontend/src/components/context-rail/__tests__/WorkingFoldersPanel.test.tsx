import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkingFoldersPanel } from '../WorkingFoldersPanel';
import { useCitationsForThread } from '@/hooks';
import { useProjectWorkingFolders } from '../hooks/useProjectWorkingFolders';

vi.mock('@/hooks', () => ({
  useCitationsForThread: vi.fn(),
}));
vi.mock('../hooks/useProjectWorkingFolders', () => ({
  useProjectWorkingFolders: vi.fn(),
}));

const mockedUseCitationsForThread = vi.mocked(useCitationsForThread);
const mockedUseProjectWorkingFolders = vi.mocked(useProjectWorkingFolders);

describe('WorkingFoldersPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseCitationsForThread.mockReturnValue({
      allCitations: [],
      relatedResults: [],
      activeDocument: null,
    });
    mockedUseProjectWorkingFolders.mockReturnValue({
      documents: undefined,
      notes: undefined,
      drafts: undefined,
      isLoading: false,
      errors: {},
    });
  });

  it('renders empty state when no project is bound', () => {
    render(<WorkingFoldersPanel />);
    expect(
      screen.getByText(/no files yet — cited sources will appear here/i)
    ).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });

  it('renders all four folders when the project has documents, notes, and drafts', () => {
    mockedUseProjectWorkingFolders.mockReturnValue({
      documents: [{ id: 'd1', title: 'Paper A' }],
      notes: [{ id: 'n1', title: 'Outline', isPinned: true }],
      drafts: [{ id: 'dr1', title: 'v1 draft', version: 1 }],
      isLoading: false,
      errors: {},
    });
    render(<WorkingFoldersPanel projectId="p1" />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Drafts')).toBeInTheDocument();
    expect(screen.getByText('Paper A')).toBeInTheDocument();
  });

  it('hides Sources/Notes/Drafts when their lists are empty', () => {
    mockedUseProjectWorkingFolders.mockReturnValue({
      documents: [],
      notes: [],
      drafts: [],
      isLoading: false,
      errors: {},
    });
    render(<WorkingFoldersPanel projectId="p1" />);
    expect(
      screen.getByText(/no files yet — cited sources will appear here/i)
    ).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });
});
