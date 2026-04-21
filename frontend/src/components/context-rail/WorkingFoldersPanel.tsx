'use client';

import { useCitationsForThread } from '@/hooks';
import { CollapsibleCard } from './CollapsibleCard';
import { FolderTree } from './folder-tree/FolderTree';
import type { Node } from './folder-tree/types';
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

/**
 * Cowork-style folder tree. Project-scoped when `projectId` is set
 * (shows `This thread` + `Sources`/`Notes`/`Drafts`, empty slots hidden);
 * otherwise falls back to a thread-only view with a CTA to attach a project.
 */
export function WorkingFoldersPanel({
  projectId,
  workspaceName,
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
      badge={
        totalFiles > 0
          ? `${totalFiles} file${totalFiles === 1 ? '' : 's'}`
          : undefined
      }
    >
      <FolderTree nodes={tree} />
      {!projectId && (
        <a
          href="/projects"
          className="mt-3 inline-flex items-center gap-1 text-[13px]"
          style={{
            color: 'var(--nous-sol)',
            fontFamily: 'var(--nous-font-ui)',
          }}
        >
          Attach this chat to a project →
        </a>
      )}
      {workspaceName && (
        <p
          className="mt-3 text-[11px]"
          style={{
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-ui)',
          }}
        >
          Workspace · {workspaceName}
        </p>
      )}
    </CollapsibleCard>
  );
}
