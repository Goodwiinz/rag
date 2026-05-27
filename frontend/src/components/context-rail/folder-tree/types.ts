export type FileIcon = 'doc' | 'pdf' | 'book' | 'note' | 'draft';

export interface FolderNode {
  kind: 'folder';
  id: string;
  label: string;
  badge?: string;
  defaultOpen?: boolean;
  children: Node[];
}

export interface FileNode {
  kind: 'file';
  id: string;
  label: string;
  icon: FileIcon;
  meta?: string;
  onSelect: () => void;
}

export type Node = FolderNode | FileNode;
