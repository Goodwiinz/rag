'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  ExternalLink,
  FileText,
  Quote,
  Search,
  X,
} from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Citation, getCitationIdentifier } from '@/utils/citationParser';

interface CitationPanelProps {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
  /** Open the source document for a citation. */
  onCitationClick?: (citation: Citation) => void;
  /** Insert a reference to the source into the composer. */
  onCite?: (citation: Citation) => void;
  /** Retrieval trace id for the answer these sources grounded. */
  diagnosticsTraceId?: string;
  activeCitationId?: string;
  className?: string;
}

type SortBy = 'relevance' | 'title';

interface SourceGroup {
  key: string;
  title: string;
  documentId?: string;
  externalReferenceId?: string;
  source?: string;
  topScore: number;
  chunks: Citation[];
}

const ARXIV_RE = /\d{4}\.\d{4,5}/;

function sourceMeta(c: Citation): { label: string; href?: string } {
  if (c.externalReferenceId && ARXIV_RE.test(c.externalReferenceId)) {
    return {
      label: 'arXiv',
      href: `https://arxiv.org/abs/${c.externalReferenceId}`,
    };
  }
  if (c.source && /^https?:\/\//.test(c.source)) {
    return { label: 'Web', href: c.source };
  }
  if (c.documentId) return { label: 'PDF' };
  if (c.externalReferenceId) return { label: 'External' };
  return { label: 'Source' };
}

function groupByDocument(citations: Citation[]): SourceGroup[] {
  const map = new Map<string, SourceGroup>();
  for (const c of citations) {
    const key = getCitationIdentifier(c);
    const existing = map.get(key);
    if (existing) {
      existing.chunks.push(c);
      existing.topScore = Math.max(existing.topScore, c.score);
    } else {
      map.set(key, {
        key,
        title: c.title,
        documentId: c.documentId,
        externalReferenceId: c.externalReferenceId,
        source: c.source,
        topScore: c.score,
        chunks: [c],
      });
    }
  }
  for (const g of map.values()) {
    g.chunks.sort((a, b) => b.score - a.score);
  }
  return [...map.values()];
}

/** Thin relevance meter: a sol-filled bar plus the percentage. */
function Relevance({ score, wide }: { score: number; wide?: boolean }) {
  const pct = Math.round(score * 100);
  return (
    <span className="inline-flex items-center gap-1.5 shrink-0">
      <span
        className="block rounded-sm overflow-hidden"
        style={{
          width: wide ? '44px' : '32px',
          height: '3px',
          background: 'var(--nous-border-1)',
        }}
      >
        <span
          className="block h-full origin-left rounded-sm"
          style={{
            width: `${pct}%`,
            background: 'var(--nous-sol)',
          }}
        />
      </span>
      <span
        className="font-nous-mono text-[10px] tabular-nums"
        style={{ color: 'var(--nous-fg-3)' }}
      >
        {pct}%
      </span>
    </span>
  );
}

function SourceGroupRow({
  group,
  expanded,
  active,
  reduce,
  onToggle,
  onOpen,
  onCite,
}: {
  group: SourceGroup;
  expanded: boolean;
  active: boolean;
  reduce: boolean;
  onToggle: () => void;
  onOpen?: (c: Citation) => void;
  onCite?: (c: Citation) => void;
}) {
  const meta = sourceMeta(group.chunks[0]);
  const headingId = `src-${group.key}`;

  return (
    <div className="border-b" style={{ borderColor: 'var(--nous-border-1)' }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={`${headingId}-panel`}
        id={headingId}
        className="flex w-full items-start gap-2.5 px-3 py-3 text-left transition-colors hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]"
        style={active ? { background: 'var(--nous-sol-subtle)' } : undefined}
      >
        <ChevronDown
          className={cn(
            'mt-0.5 h-3.5 w-3.5 shrink-0 transition-transform',
            expanded && 'rotate-0',
            !expanded && '-rotate-90'
          )}
          style={{ color: 'var(--nous-fg-3)' }}
          aria-hidden
        />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span
              className="font-nous-mono text-[9px] uppercase rounded-sm px-1.5 py-0.5 shrink-0"
              style={{
                letterSpacing: '0.08em',
                background: 'var(--nous-bg-1)',
                border: '1px solid var(--nous-border-1)',
                color: 'var(--nous-fg-3)',
              }}
            >
              {meta.label}
            </span>
            {group.chunks.length > 1 && (
              <span
                className="font-nous-mono text-[10px] tabular-nums shrink-0"
                style={{ color: 'var(--nous-fg-3)' }}
              >
                {group.chunks.length} passages
              </span>
            )}
          </span>
          <span
            className="mt-1 block font-nous-ui text-[13px] font-medium leading-snug"
            style={{ color: 'var(--nous-fg-1)' }}
          >
            {group.title}
          </span>
        </span>
        <Relevance score={group.topScore} wide />
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            id={`${headingId}-panel`}
            role="region"
            aria-labelledby={headingId}
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="space-y-3 pb-3 pl-8 pr-3">
              {group.chunks.map((chunk, i) =>
                chunk.content ? (
                  <figure key={i} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <Quote
                        className="h-3 w-3 shrink-0"
                        style={{ color: 'var(--nous-fg-3)' }}
                        aria-hidden
                      />
                      <Relevance score={chunk.score} />
                    </div>
                    <blockquote
                      className="font-nous-body text-[13px] leading-relaxed"
                      style={{ color: 'var(--nous-fg-2)' }}
                    >
                      {chunk.content}
                    </blockquote>
                  </figure>
                ) : null
              )}

              <div className="flex flex-wrap items-center gap-2 pt-0.5">
                {group.documentId && onOpen && (
                  <button
                    type="button"
                    onClick={() => onOpen(group.chunks[0])}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-nous-mono text-[10px] transition-colors hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]"
                    style={{
                      border: '1px solid var(--nous-border-1)',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    Open document
                    <ArrowUpRight className="h-3 w-3" />
                  </button>
                )}
                {meta.href && (
                  <a
                    href={meta.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-nous-mono text-[10px] transition-colors hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]"
                    style={{
                      border: '1px solid var(--nous-border-1)',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    {meta.label}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {onCite && (
                  <button
                    type="button"
                    onClick={() => onCite(group.chunks[0])}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-nous-mono text-[10px] transition-colors hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]"
                    style={{
                      border: '1px solid var(--nous-border-1)',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    Cite
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * Sources panel: the "show your work" view for a RAG answer. Citations are
 * grouped by document; each document expands to its retrieved passages with a
 * relevance meter, and offers Open / external / Cite actions. The footer links
 * to the retrieval trace.
 */
export function CitationPanel({
  citations,
  isOpen,
  onClose,
  onCitationClick,
  onCite,
  diagnosticsTraceId,
  activeCitationId,
  className,
}: CitationPanelProps) {
  const reduce = useReducedMotion();
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('relevance');
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const groups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const filtered = q
      ? citations.filter(
          (c) =>
            c.title.toLowerCase().includes(q) ||
            c.content?.toLowerCase().includes(q) ||
            c.source?.toLowerCase().includes(q)
        )
      : citations;
    const grouped = groupByDocument(filtered);
    grouped.sort((a, b) =>
      sortBy === 'relevance'
        ? b.topScore - a.topScore
        : a.title.localeCompare(b.title)
    );
    return grouped;
  }, [citations, searchQuery, sortBy]);

  // Expand the active document (or the top one) when the panel opens.
  useEffect(() => {
    if (!isOpen) return;
    const activeGroup = activeCitationId
      ? groups.find((g) => g.key === activeCitationId)
      : undefined;
    setExpandedKey(activeGroup?.key ?? groups[0]?.key ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, citations]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          aria-label="Sources"
          initial={reduce ? { opacity: 0 } : { x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={reduce ? { opacity: 0 } : { x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 26, stiffness: 300 }}
          className={cn(
            'fixed right-0 top-0 bottom-0 z-50 flex w-[400px] max-w-[90vw] flex-col',
            'bg-[var(--nous-bg-1)] border-l border-[var(--nous-border-1)]',
            className
          )}
          style={{ boxShadow: '-20px 0 60px rgba(10, 10, 14, 0.18)' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-4 py-3">
            <div className="flex items-center gap-2">
              <BookOpen
                className="h-4 w-4"
                style={{ color: 'var(--nous-sol)' }}
                aria-hidden
              />
              <h2
                className="font-nous-ui text-sm font-semibold"
                style={{ color: 'var(--nous-fg-1)' }}
              >
                Sources
              </h2>
              <span
                className="font-nous-mono text-[10px] tabular-nums rounded-full px-1.5 py-0.5"
                style={{
                  background: 'var(--nous-sol-subtle)',
                  color: 'var(--nous-fg-accent-safe)',
                }}
              >
                {groups.length}
              </span>
            </div>
            <IconButton
              icon={<X className="h-4 w-4" />}
              label="Close sources panel"
              onClick={onClose}
              className="h-8 w-8 text-[var(--nous-fg-3)] hover:bg-[var(--nous-aurum)] hover:text-[var(--nous-fg-1)]"
            />
          </div>

          {/* Search + sort */}
          <div className="space-y-3 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] px-4 py-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--nous-fg-3)]" />
              <Input
                type="text"
                placeholder="Search sources…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={cn(
                  'h-9 pl-9 font-nous-mono text-sm',
                  'bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]',
                  'text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)]',
                  'focus:border-[var(--nous-sol)]/30 focus:ring-[var(--nous-sol)]/10'
                )}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="font-nous-mono text-[10px] text-[var(--nous-fg-3)]">
                {groups.length} {groups.length === 1 ? 'document' : 'documents'}
              </span>
              <button
                type="button"
                onClick={() =>
                  setSortBy((s) => (s === 'relevance' ? 'title' : 'relevance'))
                }
                className="rounded-md px-2 py-1 font-nous-mono text-[10px] text-[var(--nous-fg-3)] transition-colors hover:bg-[var(--nous-aurum)] hover:text-[var(--nous-fg-1)] dark:hover:bg-[var(--nous-ember)]"
              >
                {sortBy === 'relevance' ? 'By relevance' : 'By title'}
              </button>
            </div>
          </div>

          {/* Grouped sources */}
          <div className="nous-scrollbar flex-1 overflow-y-auto">
            {groups.length === 0 ? (
              <div className="flex h-40 flex-col items-center justify-center px-6 text-center">
                <FileText
                  className="mb-2 h-9 w-9"
                  style={{ color: 'var(--nous-fg-3)' }}
                  aria-hidden
                />
                <p className="font-nous-mono text-xs text-[var(--nous-fg-3)]">
                  {searchQuery
                    ? 'No sources match your search.'
                    : 'No sources for this answer.'}
                </p>
              </div>
            ) : (
              groups.map((group) => (
                <SourceGroupRow
                  key={group.key}
                  group={group}
                  expanded={expandedKey === group.key}
                  active={activeCitationId === group.key}
                  reduce={!!reduce}
                  onToggle={() =>
                    setExpandedKey((k) => (k === group.key ? null : group.key))
                  }
                  onOpen={onCitationClick}
                  onCite={onCite}
                />
              ))
            )}
          </div>

          {/* Footer: retrieval trace */}
          <div className="border-t border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-4 py-2.5">
            {diagnosticsTraceId ? (
              <a
                href={`/diagnostics?trace=${encodeURIComponent(diagnosticsTraceId)}`}
                className="flex items-center justify-center gap-1.5 font-nous-mono text-[10px] uppercase tracking-widest text-[var(--nous-fg-3)] transition-colors hover:text-[var(--nous-fg-accent-safe)]"
              >
                <Activity className="h-3 w-3" />
                View retrieval trace
              </a>
            ) : (
              <p className="text-center font-nous-mono text-[9px] uppercase tracking-widest text-[var(--nous-fg-3)]">
                Grounded in your sources
              </p>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

export default CitationPanel;
