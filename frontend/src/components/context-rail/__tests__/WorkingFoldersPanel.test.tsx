/* eslint-disable @typescript-eslint/no-require-imports */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkingFoldersPanel } from '../WorkingFoldersPanel';

vi.mock('@/hooks', () => ({
  useCitationsForThread: vi.fn(),
}));
vi.mock('../hooks/useProjectWorkingFolders', () => ({
  useProjectWorkingFolders: vi.fn(),
}));

const { useCitationsForThread } = require('@/hooks');
const { useProjectWorkingFolders } = require('../hooks/useProjectWorkingFolders');

describe('WorkingFoldersPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useCitationsForThread.mockReturnValue({
      allCitations: [],
      relatedResults: [],
      activeDocument: null,
    });
    useProjectWorkingFolders.mockReturnValue({
      documents: undefined,
      notes: undefined,
      drafts: undefined,
      isLoading: false,
      errors: {},
    });
  });

  it('renders only "This thread" and the attach CTA when no project is bound', () => {
    render(<WorkingFoldersPanel />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText(/attach this chat to a project/i)).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });

  it('renders all four folders when the project has documents, notes, and drafts', () => {
    useProjectWorkingFolders.mockReturnValue({
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
    useProjectWorkingFolders.mockReturnValue({
      documents: [],
      notes: [],
      drafts: [],
      isLoading: false,
      errors: {},
    });
    render(<WorkingFoldersPanel projectId="p1" />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Drafts')).not.toBeInTheDocument();
  });
});
