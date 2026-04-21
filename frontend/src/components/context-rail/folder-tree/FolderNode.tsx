'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { FileRow } from './FileRow';
import type { FolderNode as FolderNodeType, Node } from './types';

export function FolderNode({ node }: { node: FolderNodeType }) {
  const [open, setOpen] = useState(node.defaultOpen ?? true);

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 py-1"
        aria-expanded={open}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 transition-transform',
            !open && '-rotate-90'
          )}
          style={{ color: 'var(--nous-fg-3)' }}
        />
        <span
          className="text-[13px] font-medium"
          style={{
            color: 'var(--nous-fg-1)',
            fontFamily: 'var(--nous-font-ui)',
          }}
        >
          {node.label}
        </span>
        {node.badge && (
          <span
            className="text-[11px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {node.badge}
          </span>
        )}
      </button>

      {open && node.children.length > 0 && (
        <ul className="pl-5">
          {node.children.map((child) => renderNode(child))}
        </ul>
      )}
    </li>
  );
}

function renderNode(node: Node) {
  if (node.kind === 'folder') {
    return <FolderNode key={node.id} node={node} />;
  }
  return <FileRow key={node.id} node={node} />;
}
