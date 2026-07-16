'use client';

import { useCitationsForThread } from '@/hooks';
import { Folder } from 'lucide-react';
import { CollapsibleCard } from './CollapsibleCard';
import { FolderTree, type Node } from './folder-tree';
import { useProjectWorkingFolders } from './hooks/useProjectWorkingFolders';

export type WorkingFoldersSelection =
  | { kind: 'document'; id: string; title: string }
  | { kind: 'external'; id: string; title: string }
  | { kind: 'note'; id: string; title: string }
  | { kind: 'draft'; id: string; title: string };

interface WorkingFoldersPanelProps {
  projectId?: string;
  workspaceName?: string | null;
  onSelect?: (node: WorkingFoldersSelection) => void;
}

export function WorkingFoldersPanel({
  projectId,
  workspaceName: _workspaceName,
  onSelect,
}: WorkingFoldersPanelProps = {}) {
  const { allCitations } = useCitationsForThread();
  const { documents, notes, drafts } = useProjectWorkingFolders(projectId);

  const threadInternal = allCitations.filter((c) => c.documentId);
  const threadExternal = allCitations.filter((c) => !c.documentId);

  const thisThread: Node = {
    kind: 'folder',
    id: 'this-thread',
    label: 'This thread',
    defaultOpen: true,
    badge:
      threadInternal.length + threadExternal.length > 0
        ? String(threadInternal.length + threadExternal.length)
        : undefined,
    children: [
      ...threadInternal.map((c, i) => ({
        kind: 'file' as const,
        id: `ti-${c.id || c.documentId || i}`,
        label: c.title || 'Untitled document',
        icon: 'pdf' as const,
        onSelect: () =>
          onSelect?.({
            kind: 'document',
            id: (c.documentId ?? '') as string,
            title: c.title || 'Untitled document',
          }),
      })),
      ...threadExternal.map((c, i) => ({
        kind: 'file' as const,
        id: `te-${c.id || c.externalReferenceId || i}`,
        label: c.title || 'Untitled source',
        icon: 'book' as const,
        onSelect: () =>
          onSelect?.({
            kind: 'external',
            id: (c.externalReferenceId ?? c.id ?? '') as string,
            title: c.title || 'Untitled source',
          }),
      })),
    ],
  };

  const tree: Node[] = [thisThread];

  if (projectId && documents && documents.length > 0) {
    tree.push({
      kind: 'folder',
      id: 'sources',
      label: 'Sources',
      defaultOpen: true,
      badge: String(documents.length),
      children: documents.map((d) => ({
        kind: 'file',
        id: `src-${d.id}`,
        label: d.title ?? 'Untitled document',
        icon: 'pdf',
        onSelect: () =>
          onSelect?.({
            kind: 'document',
            id: d.id,
            title: d.title ?? 'Untitled document',
          }),
      })),
    });
  }

  if (projectId && notes && notes.length > 0) {
    const sorted = [...notes].sort(
      (a, b) => Number(b.isPinned ?? 0) - Number(a.isPinned ?? 0)
    );
    tree.push({
      kind: 'folder',
      id: 'notes',
      label: 'Notes',
      badge: String(notes.length),
      children: sorted.map((n) => ({
        kind: 'file',
        id: `note-${n.id}`,
        label: n.title,
        icon: 'note',
        meta: n.isPinned ? '📌' : undefined,
        onSelect: () => onSelect?.({ kind: 'note', id: n.id, title: n.title }),
      })),
    });
  }

  if (projectId && drafts && drafts.length > 0) {
    tree.push({
      kind: 'folder',
      id: 'drafts',
      label: 'Drafts',
      badge: String(drafts.length),
      children: drafts.map((d) => ({
        kind: 'file',
        id: `draft-${d.id}`,
        label: d.title,
        icon: 'draft',
        meta: d.version ? `v${d.version}` : undefined,
        onSelect: () => onSelect?.({ kind: 'draft', id: d.id, title: d.title }),
      })),
    });
  }

  const totalFiles =
    threadInternal.length +
    threadExternal.length +
    (documents?.length ?? 0) +
    (notes?.length ?? 0) +
    (drafts?.length ?? 0);

  return (
    <CollapsibleCard
      title="Working folders"
      icon={<Folder className="h-3 w-3" strokeWidth={1.7} />}
      badge={totalFiles > 0 ? String(totalFiles) : undefined}
    >
      {totalFiles === 0 ? (
        <p
          className="py-2 text-[11px] text-[var(--nous-fg-3)]"
          style={{
            fontFamily: 'var(--nous-font-mono)',
            letterSpacing: '0.04em',
          }}
        >
          No files yet — cited sources will appear here.
        </p>
      ) : (
        <FolderTree nodes={tree} />
      )}
    </CollapsibleCard>
  );
}
