'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  ExternalLink,
  ListTree,
  Pin,
  PinOff,
  X,
} from 'lucide-react';
import Link from 'next/link';

import { IconButton } from '@/components/ui/icon-button';
import { ChatMarkdown } from '@/components/chat/ChatMarkdown';
import { CitationPanelBody } from '@/components/chat/CitationPanelBody';
import {
  useDraftArtifact,
  useNoteArtifact,
} from '@/components/chat/artifact-panel/useArtifactContent';
import { DocumentInlineViewer } from '@/components/documents/DocumentInlineViewer';
import { cn } from '@/lib/utils';
import { documentService } from '@/services/documentService';
import { useArtifactPanelStore, type Artifact } from '@/store/artifactPanelStore';
import type { Citation } from '@/utils/citationParser';

const ARXIV_RE = /\d{4}\.\d{4,5}/;

function externalHref(artifact: Extract<Artifact, { kind: 'external' }>) {
  if (ARXIV_RE.test(artifact.id))
    return `https://arxiv.org/abs/${artifact.id.match(ARXIV_RE)![0]}`;
  if (artifact.source && /^https?:\/\//.test(artifact.source))
    return artifact.source;
  return undefined;
}

const KIND_LABEL: Record<Artifact['kind'], string> = {
  document: 'Document',
  external: 'External',
  note: 'Note',
  draft: 'Draft',
  citations: 'Sources',
};

function artifactTitle(artifact: Artifact): string {
  return artifact.kind === 'citations' ? 'Sources' : artifact.title;
}

function DocumentArtifactBody({ documentId }: { documentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['document', documentId],
    queryFn: async () => (await documentService.getDocument(documentId)).data,
  });

  if (isLoading) {
    return (
      <div className="p-3">
        <div className="h-[60vh] min-h-[320px] animate-pulse rounded-xl border border-(--nous-border-1) bg-(--nous-bg-2)" />
        <span className="sr-only" role="status">
          Loading document…
        </span>
      </div>
    );
  }

  if (isError || !data) {
    return <ArtifactContentError what="document" />;
  }

  return (
    <div className="p-3">
      <DocumentInlineViewer
        documentId={data.id}
        filename={data.filename || data.title}
        kind={data.file_type || data.document_type}
        mimeType={data.mime_type}
      />
    </div>
  );
}

function ExternalArtifactBody({
  artifact,
}: {
  artifact: Extract<Artifact, { kind: 'external' }>;
}) {
  const href = externalHref(artifact);
  return (
    <div className="m-3 flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-(--nous-border-1) bg-(--nous-bg-2) px-6 py-10 text-center">
      <p className="font-nous-ui text-sm font-medium text-(--nous-fg-1)">
        {artifact.title}
      </p>
      <p className="mt-1 max-w-sm text-xs text-(--nous-fg-3)">
        This source lives outside your corpus, so it can&apos;t be previewed
        inline.
      </p>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-5 inline-flex items-center gap-2 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-1) px-4 py-2 text-sm font-medium text-(--nous-fg-2) transition-colors hover:bg-(--nous-aurum) hover:text-(--nous-fg-1) dark:hover:bg-(--nous-ember) focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
        >
          Open source
          <ExternalLink aria-hidden="true" className="h-4 w-4" />
        </a>
      )}
    </div>
  );
}

function ArtifactContentSkeleton() {
  return (
    <div className="p-3">
      <div className="h-[50vh] min-h-[280px] animate-pulse rounded-xl border border-(--nous-border-1) bg-(--nous-bg-2)" />
      <span className="sr-only" role="status">
        Loading…
      </span>
    </div>
  );
}

function ArtifactContentError({ what }: { what: string }) {
  return (
    <div
      role="alert"
      className="m-3 flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 px-6 text-center"
    >
      <AlertTriangle
        aria-hidden="true"
        className="mb-3 h-8 w-8 text-destructive"
      />
      <p className="text-sm font-medium text-(--nous-fg-1)">
        Couldn&apos;t load this {what}
      </p>
      <p className="mt-1 max-w-sm text-xs text-(--nous-fg-3)">
        It may have been deleted, or you may not have access to it.
      </p>
    </div>
  );
}

function NoteArtifactBody({
  artifact,
}: {
  artifact: Extract<Artifact, { kind: 'note' }>;
}) {
  const { data, isLoading, isError } = useNoteArtifact(
    artifact.projectId,
    artifact.id
  );
  if (isLoading) return <ArtifactContentSkeleton />;
  if (isError || !data) return <ArtifactContentError what="note" />;
  return (
    <div className="p-4 font-nous-body text-sm leading-relaxed text-(--nous-fg-1)">
      <ChatMarkdown content={data.content} />
    </div>
  );
}

function DraftArtifactBody({
  artifact,
}: {
  artifact: Extract<Artifact, { kind: 'draft' }>;
}) {
  const { data, isLoading, isError } = useDraftArtifact(
    artifact.projectId,
    artifact.id
  );
  if (isLoading) return <ArtifactContentSkeleton />;
  if (isError || !data) return <ArtifactContentError what="draft" />;
  return (
    <div className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 font-nous-mono text-[10px] text-(--nous-fg-3)">
        <span
          className="rounded-sm border border-(--nous-border-1) bg-(--nous-bg-2) px-1.5 py-0.5 uppercase"
          style={{ letterSpacing: '0.08em' }}
        >
          v{data.version}
          {data.is_current ? ' · current' : ''}
        </span>
        <span className="tabular-nums">{data.word_count} words</span>
        <span className="tabular-nums">{data.citation_count} citations</span>
      </div>
      <div className="font-nous-body text-sm leading-relaxed text-(--nous-fg-1)">
        <ChatMarkdown content={data.content} />
      </div>
    </div>
  );
}

interface ArtifactPanelProps {
  artifact: Artifact;
  /**
   * Codex-style context toggle: the docked panel occupies the rail's slot,
   * so the rail becomes an overlay behind this button. Omitted on viewports
   * where the rail never rendered.
   */
  onToggleRail?: () => void;
  railOpen?: boolean;
  className?: string;
}

/**
 * The chat split-view's right pane: shows the artifact in focus (document,
 * external source — notes/drafts/citations arrive in follow-up PRs) while the
 * chat column stays mounted beside it. Docked at lg+; a bottom sheet below.
 */
export function ArtifactPanel({
  artifact,
  onToggleRail,
  railOpen,
  className,
}: ArtifactPanelProps) {
  const closePanel = useArtifactPanelStore((s) => s.closePanel);
  const pinned = useArtifactPanelStore((s) => s.pinned);
  const togglePin = useArtifactPanelStore((s) => s.togglePin);
  const openArtifact = useArtifactPanelStore((s) => s.openArtifact);

  // "Open document" inside a sources view focuses that document here — the
  // split-view stays put, the panel just changes what it shows.
  const handleOpenCitedDocument = (citation: Citation) => {
    if (citation.documentId) {
      openArtifact({
        kind: 'document',
        id: citation.documentId,
        title: citation.title || 'Untitled document',
      });
    }
  };

  // The composer lives in a different subtree (ChatSurface); reuse the
  // existing 'populate-chat-input' bridge with append semantics so citing
  // never clobbers a draft the user is typing.
  const handleCite = (citation: Citation) => {
    window.dispatchEvent(
      new CustomEvent('populate-chat-input', {
        detail: { text: `"${citation.title}"`, mode: 'append' },
      })
    );
  };

  const fullPageHref =
    artifact.kind === 'document' ? `/documents/${artifact.id}` : undefined;

  return (
    <aside
      role="region"
      aria-label="Artifact viewer"
      onKeyDown={(e) => {
        if (e.key === 'Escape') closePanel();
      }}
      className={cn(
        'flex flex-col bg-(--nous-bg-1)',
        // Desktop: docked column in the layout's right slot.
        'lg:static lg:h-full lg:w-[min(45vw,640px)] lg:shrink-0',
        'lg:border-l lg:border-(--nous-border-1)',
        // Below lg: bottom sheet so the transcript stays reachable.
        'max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-50 max-lg:h-[85dvh]',
        'max-lg:rounded-t-(--nous-radius-xl) max-lg:border-t max-lg:border-(--nous-border-1)',
        'max-lg:shadow-(--nous-shadow-lg)',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-(--nous-border-1) bg-(--nous-bg-2) px-3 py-2.5">
        <span
          className="font-nous-mono shrink-0 rounded-sm border border-(--nous-border-1) bg-(--nous-bg-1) px-1.5 py-0.5 text-[9px] uppercase text-(--nous-fg-3)"
          style={{ letterSpacing: '0.08em' }}
        >
          {KIND_LABEL[artifact.kind]}
        </span>
        <h2
          className="font-nous-ui min-w-0 flex-1 truncate text-sm font-semibold text-(--nous-fg-1)"
          title={artifactTitle(artifact)}
        >
          {artifactTitle(artifact)}
        </h2>
        <div className="flex shrink-0 items-center gap-0.5">
          {fullPageHref && (
            <Link
              href={fullPageHref}
              aria-label="Open full page"
              title="Open full page"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-(--nous-fg-3) transition-colors hover:bg-(--nous-aurum) hover:text-(--nous-fg-1) focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ExternalLink aria-hidden="true" className="h-4 w-4" />
            </Link>
          )}
          <IconButton
            icon={
              pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />
            }
            label={
              pinned
                ? 'Unpin — allow the agent to change this view'
                : 'Pin this artifact'
            }
            aria-pressed={pinned}
            onClick={togglePin}
            className={cn(
              'h-8 w-8 hover:bg-(--nous-aurum)',
              pinned
                ? 'text-(--nous-fg-accent-safe)'
                : 'text-(--nous-fg-3) hover:text-(--nous-fg-1)'
            )}
          />
          {onToggleRail && (
            <IconButton
              icon={<ListTree className="h-4 w-4" />}
              label={railOpen ? 'Hide context rail' : 'Show context rail'}
              aria-pressed={railOpen}
              onClick={onToggleRail}
              className="h-8 w-8 text-(--nous-fg-3) hover:bg-(--nous-aurum) hover:text-(--nous-fg-1) max-lg:hidden"
            />
          )}
          <IconButton
            icon={<X className="h-4 w-4" />}
            label="Close artifact panel"
            onClick={closePanel}
            className="h-8 w-8 text-(--nous-fg-3) hover:bg-(--nous-aurum) hover:text-(--nous-fg-1)"
          />
        </div>
      </div>

      {/* Body */}
      <div className="nous-scrollbar flex-1 overflow-y-auto">
        {artifact.kind === 'document' && (
          <DocumentArtifactBody documentId={artifact.id} />
        )}
        {artifact.kind === 'external' && (
          <ExternalArtifactBody artifact={artifact} />
        )}
        {artifact.kind === 'citations' && (
          <CitationPanelBody
            citations={artifact.citations}
            activeCitationId={artifact.activeCitationId}
            diagnosticsTraceId={artifact.traceId}
            onCitationClick={handleOpenCitedDocument}
            onCite={handleCite}
          />
        )}
        {artifact.kind === 'note' && <NoteArtifactBody artifact={artifact} />}
        {artifact.kind === 'draft' && <DraftArtifactBody artifact={artifact} />}
      </div>
    </aside>
  );
}
