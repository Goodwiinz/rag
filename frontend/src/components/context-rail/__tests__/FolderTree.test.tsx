import { fireEvent, render, screen } from '@testing-library/react';
import { FolderTree } from '../folder-tree/FolderTree';
import type { Node } from '../folder-tree/types';

const onSelect = jest.fn();

function buildTree(overrides: Partial<Node> = {}): Node[] {
  return [
    {
      kind: 'folder',
      id: 'thread',
      label: 'This thread',
      defaultOpen: true,
      children: [
        {
          kind: 'file',
          id: 'doc-1',
          label: 'Paper A',
          icon: 'pdf',
          onSelect: () => onSelect({ id: 'doc-1' }),
        },
      ],
      ...overrides,
    },
    {
      kind: 'folder',
      id: 'sources',
      label: 'Sources',
      defaultOpen: false,
      children: [
        {
          kind: 'file',
          id: 'doc-2',
          label: 'Paper B',
          icon: 'pdf',
          onSelect: () => onSelect({ id: 'doc-2' }),
        },
      ],
    },
  ];
}

describe('FolderTree', () => {
  beforeEach(() => onSelect.mockClear());

  it('renders every folder label', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.getByText('This thread')).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
  });

  it('shows children of default-open folders', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.getByText('Paper A')).toBeInTheDocument();
  });

  it('hides children of default-closed folders until toggled', () => {
    render(<FolderTree nodes={buildTree()} />);
    expect(screen.queryByText('Paper B')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Sources/ }));
    expect(screen.getByText('Paper B')).toBeInTheDocument();
  });

  it('collapses a default-open folder when header is clicked', () => {
    render(<FolderTree nodes={buildTree()} />);
    fireEvent.click(screen.getByRole('button', { name: /^This thread/ }));
    expect(screen.queryByText('Paper A')).not.toBeInTheDocument();
  });

  it('fires the leaf onSelect with the right node', () => {
    render(<FolderTree nodes={buildTree()} />);
    fireEvent.click(screen.getByText('Paper A'));
    expect(onSelect).toHaveBeenCalledWith({ id: 'doc-1' });
  });
});
