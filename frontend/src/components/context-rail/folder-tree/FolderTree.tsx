'use client';

import { FileRow } from './FileRow';
import { FolderNode } from './FolderNode';
import type { Node } from './types';

interface FolderTreeProps {
  nodes: Node[];
}

export function FolderTree({ nodes }: FolderTreeProps) {
  return (
    <ul>
      {nodes.map((n) =>
        n.kind === 'folder' ? (
          <FolderNode key={n.id} node={n} />
        ) : (
          <FileRow key={n.id} node={n} />
        )
      )}
    </ul>
  );
}
