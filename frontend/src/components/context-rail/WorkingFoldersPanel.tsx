'use client';

import { useCitationsForThread } from '@/hooks';
import { BookOpen, FileText, FolderOpen } from 'lucide-react';
import { CollapsibleCard } from './CollapsibleCard';

interface WorkingFoldersPanelProps {
  /** Optional workspace name to use as the top-level folder label. */
  workspaceName?: string | null;
}

/**
 * Cowork-style "Working folders" card. NOUS doesn't have a real filesystem
 * tree, so we surface a workspace-rooted view of what the thread has touched:
 *   - Thread documents: anything with a `documentId` (uploaded to the
 *     workspace and retrieved via RAG)
 *   - External sources: arXiv / web citations from assistant messages
 * The card is always rendered — an empty state prompts the user to attach
 * a file or ask a RAG question.
 */
export function WorkingFoldersPanel({
  workspaceName,
}: WorkingFoldersPanelProps = {}) {
  const { allCitations } = useCitationsForThread();

  const internal = allCitations.filter((c) => c.documentId);
  const external = allCitations.filter((c) => !c.documentId);
  const total = internal.length + external.length;

  const rootLabel = workspaceName ?? 'Workspace';

  return (
    <CollapsibleCard
      title="Working folders"
      badge={total > 0 ? `${total} file${total === 1 ? '' : 's'}` : undefined}
    >
      <div className="flex items-center gap-2 mb-2">
        <FolderOpen
          className="h-4 w-4 shrink-0"
          style={{ color: 'var(--nous-fg-3)' }}
        />
        <span
          className="text-[13px] font-medium truncate"
          style={{
            color: 'var(--nous-fg-1)',
            fontFamily: 'var(--nous-font-ui)',
          }}
          title={rootLabel}
        >
          {rootLabel}
        </span>
      </div>

      {total === 0 ? (
        <p
          className="pl-6 text-[13px]"
          style={{
            color: 'var(--nous-fg-3)',
            fontFamily: 'var(--nous-font-body)',
          }}
        >
          No files yet. Attach documents with the paperclip in the composer, or
          ask a question to pull sources from the workspace.
        </p>
      ) : (
        <div className="pl-6 space-y-3">
          {internal.length > 0 && (
            <div>
              <div
                className="text-[11px] uppercase tracking-wider mb-2"
                style={{ color: 'var(--nous-fg-3)' }}
              >
                Thread documents
              </div>
              <ul className="space-y-1">
                {internal.map((c, idx) => (
                  <li
                    key={c.id || c.documentId || idx}
                    className="flex items-center gap-3 py-1"
                    style={{ fontFamily: 'var(--nous-font-body)' }}
                  >
                    <FileText
                      className="w-4 h-4 shrink-0"
                      style={{ color: 'var(--nous-sol)' }}
                    />
                    <span
                      className="text-[14px] truncate"
                      style={{ color: 'var(--nous-fg-1)' }}
                      title={c.title}
                    >
                      {c.title || 'Untitled document'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {external.length > 0 && (
            <div>
              <div
                className="text-[11px] uppercase tracking-wider mb-2"
                style={{ color: 'var(--nous-fg-3)' }}
              >
                External sources
              </div>
              <ul className="space-y-1">
                {external.map((c, idx) => (
                  <li
                    key={c.id || c.externalReferenceId || idx}
                    className="flex items-center gap-3 py-1"
                    style={{ fontFamily: 'var(--nous-font-body)' }}
                  >
                    <BookOpen
                      className="w-4 h-4 shrink-0"
                      style={{ color: 'var(--nous-corona)' }}
                    />
                    <span
                      className="text-[14px] truncate"
                      style={{ color: 'var(--nous-fg-1)' }}
                      title={c.title}
                    >
                      {c.title || 'Untitled source'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </CollapsibleCard>
  );
}
