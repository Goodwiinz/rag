'use client';

import { useState, useMemo, useCallback, useRef, useEffect, memo } from 'react';
import { FixedSizeList as List } from 'react-window';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Edit, BookOpen, ExternalLink } from 'lucide-react';
import type { CitationResponse } from '@/types/research';
import { cn } from '@/lib/utils';

export interface CitationListProps {
  citations: CitationResponse[];
  onEdit?: (citation: CitationResponse) => void;
  onDelete?: (citationId: string) => void;
  className?: string;
  showActions?: boolean;
  maxHeight?: string;
  /** Height in pixels for virtualized list (default: 600) */
  height?: number;
  /** Threshold for enabling virtualization (default: 100) */
  virtualizationThreshold?: number;
}

// Get source badge color based on metadata source
const getSourceBadgeColor = (source?: string) => {
  switch (source) {
    case 'arxiv':
      return 'bg-sol/10 text-sol border-sol/20';
    case 'semantic_scholar':
      return 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20';
    case 'crossref':
      return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
    default:
      return 'bg-gray-500/10 text-muted-foreground border-border/20';
  }
};

// Item data for virtualized list
interface CitationItemData {
  citations: CitationResponse[];
  expandedIds: Set<string>;
  showActions: boolean;
  onEdit?: (citation: CitationResponse) => void;
  onToggleExpand: (id: string) => void;
}

// Individual citation item renderer for virtualized list
const CitationItem = memo<{
  index: number;
  style: React.CSSProperties;
  data: CitationItemData;
}>(({ index, style, data }) => {
  const citation = data.citations[index];
  const isExpanded = data.expandedIds.has(citation.id);
  const hasAbstract = citation.abstract && citation.abstract.trim().length > 0;

  return (
    <div style={{ ...style, paddingBottom: '12px' }}>
      <div className="rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] hover:bg-[var(--nous-bg-3)] transition-all h-full overflow-hidden">
        <div className="p-4 h-full overflow-y-auto">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              {/* Title */}
              <h3 className="text-sm font-mono font-bold text-[var(--nous-fg-1)] line-clamp-2 mb-2">
                {citation.documentTitle || 'Untitled'}
              </h3>

              {/* Authors and Year */}
              <p className="text-xs font-mono text-[var(--nous-fg-3)]">
                {citation.authors && citation.authors.length > 0
                  ? citation.authors.slice(0, 3).join(', ') +
                    (citation.authors.length > 3 ? ', et al.' : '')
                  : 'Unknown authors'}
                {citation.year && ` (${citation.year})`}
              </p>

              {/* Venue */}
              {citation.venue && (
                <p className="text-xs font-mono text-muted-foreground mt-1 truncate">
                  {citation.venue}
                </p>
              )}
            </div>

            {/* Status Badges */}
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              {citation.needsReview && (
                <span className="px-2 py-1 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-[var(--nous-helios)]/10 text-[var(--nous-helios)] border border-[var(--nous-helios)]/20 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Needs Review
                </span>
              )}

              {data.showActions && data.onEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => data.onEdit?.(citation)}
                  className="h-7 px-2 text-xs font-mono text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)]"
                >
                  <Edit className="w-3.5 h-3.5 mr-1" />
                  Edit
                </Button>
              )}
            </div>
          </div>

          {/* Identifiers (ArXiv, DOI) */}
          {(citation.arxivId || citation.doi) && (
            <div className="mt-3 pt-3 border-t border-[var(--nous-border-1)] flex flex-wrap gap-2">
              {citation.arxivId && (
                <a
                  href={`https://arxiv.org/abs/${citation.arxivId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--nous-sol)]/5 text-[var(--nous-sol)] border border-[var(--nous-sol)]/20 hover:bg-[var(--nous-sol)]/10 transition-all flex items-center gap-1"
                >
                  ArXiv: {citation.arxivId}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {citation.doi && (
                <a
                  href={`https://doi.org/${citation.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/5 text-cyan-500 border border-cyan-500/20 hover:bg-cyan-500/10 transition-all flex items-center gap-1"
                >
                  DOI: {citation.doi}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {citation.metadataSource && (
                <span
                  className={cn(
                    'px-2 py-0.5 rounded text-[10px] font-mono border',
                    getSourceBadgeColor(citation.metadataSource)
                  )}
                >
                  Source: {citation.metadataSource.replace('_', ' ')}
                </span>
              )}
            </div>
          )}

          {/* Abstract (Expandable) - Compact view in virtualized mode */}
          {hasAbstract && (
            <div className="mt-3 pt-3 border-t border-[var(--nous-border-1)]">
              <button
                onClick={() => data.onToggleExpand(citation.id)}
                className="text-xs font-mono text-[var(--nous-sol)] hover:underline mb-2"
              >
                {isExpanded ? 'Hide' : 'Show'} Abstract
              </button>
              {isExpanded && (
                <p className="text-xs font-mono text-[var(--nous-fg-3)] leading-relaxed line-clamp-4">
                  {citation.abstract}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

CitationItem.displayName = 'CitationItem';

/**
 * CitationList Component
 *
 * Displays a list of research citations with Terminal Observatory theme.
 * Uses react-window for virtualization when list exceeds threshold (default: 100 items).
 *
 * Features:
 * - Citation metadata display (title, authors, year, venue)
 * - "Needs review" badges for incomplete metadata
 * - Edit button for manual correction
 * - ArXiv ID and DOI badges
 * - Source attribution (arxiv, semantic_scholar, crossref)
 * - Virtual scrolling for 500+ items (performance optimized)
 * - Scrollable list with max height
 */
export function CitationList({
  citations,
  onEdit,
  onDelete,
  className,
  showActions = true,
  maxHeight = '600px',
  height = 600,
  virtualizationThreshold = 100,
}: CitationListProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const listRef = useRef<List<CitationItemData>>(null);

  const toggleExpand = useCallback((citationId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(citationId)) {
        next.delete(citationId);
      } else {
        next.add(citationId);
      }
      return next;
    });
  }, []);

  // Memoize item data for virtualized list
  const itemData = useMemo<CitationItemData>(
    () => ({
      citations,
      expandedIds,
      showActions,
      onEdit,
      onToggleExpand: toggleExpand,
    }),
    [citations, expandedIds, showActions, onEdit, toggleExpand]
  );

  // Determine if we should use virtualization
  const useVirtualization = citations.length >= virtualizationThreshold;

  // Empty state
  if (citations.length === 0) {
    return (
      <div
        className={cn(
          'text-center py-12 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]',
          className
        )}
      >
        <BookOpen className="w-12 h-12 text-foreground mx-auto mb-4" />
        <p className="font-mono text-sm text-[var(--nous-fg-3)]">
          No citations found
        </p>
        <p className="font-mono text-xs text-foreground mt-2">
          Citations will appear here after extraction
        </p>
      </div>
    );
  }

  // Non-virtualized rendering for small lists
  if (!useVirtualization) {
    return (
      <div
        className={cn('space-y-3', className)}
        style={{ maxHeight, overflowY: 'auto' }}
      >
        {citations.map((citation) => {
          const isExpanded = expandedIds.has(citation.id);
          const hasAbstract =
            citation.abstract && citation.abstract.trim().length > 0;

          return (
            <div
              key={citation.id}
              className="rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] hover:bg-[var(--nous-bg-3)] transition-all"
            >
              {/* Main Citation Info */}
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {/* Title */}
                    <h3 className="text-sm font-mono font-bold text-[var(--nous-fg-1)] line-clamp-2 mb-2">
                      {citation.documentTitle || 'Untitled'}
                    </h3>

                    {/* Authors and Year */}
                    <p className="text-xs font-mono text-[var(--nous-fg-3)]">
                      {citation.authors && citation.authors.length > 0
                        ? citation.authors.slice(0, 3).join(', ') +
                          (citation.authors.length > 3 ? ', et al.' : '')
                        : 'Unknown authors'}
                      {citation.year && ` (${citation.year})`}
                    </p>

                    {/* Venue */}
                    {citation.venue && (
                      <p className="text-xs font-mono text-muted-foreground mt-1">
                        {citation.venue}
                      </p>
                    )}
                  </div>

                  {/* Status Badges */}
                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    {citation.needsReview && (
                      <span className="px-2 py-1 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-[var(--nous-helios)]/10 text-[var(--nous-helios)] border border-[var(--nous-helios)]/20 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Needs Review
                      </span>
                    )}

                    {showActions && onEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(citation)}
                        className="h-7 px-2 text-xs font-mono text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)]"
                      >
                        <Edit className="w-3.5 h-3.5 mr-1" />
                        Edit
                      </Button>
                    )}
                  </div>
                </div>

                {/* Identifiers (ArXiv, DOI) */}
                {(citation.arxivId || citation.doi) && (
                  <div className="mt-3 pt-3 border-t border-[var(--nous-border-1)] flex flex-wrap gap-2">
                    {citation.arxivId && (
                      <a
                        href={`https://arxiv.org/abs/${citation.arxivId}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--nous-sol)]/5 text-[var(--nous-sol)] border border-[var(--nous-sol)]/20 hover:bg-[var(--nous-sol)]/10 transition-all flex items-center gap-1"
                      >
                        ArXiv: {citation.arxivId}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {citation.doi && (
                      <a
                        href={`https://doi.org/${citation.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/5 text-cyan-500 border border-cyan-500/20 hover:bg-cyan-500/10 transition-all flex items-center gap-1"
                      >
                        DOI: {citation.doi}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {citation.metadataSource && (
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-mono border',
                          getSourceBadgeColor(citation.metadataSource)
                        )}
                      >
                        Source: {citation.metadataSource.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                )}

                {/* Abstract (Expandable) */}
                {hasAbstract && (
                  <div className="mt-3 pt-3 border-t border-[var(--nous-border-1)]">
                    <button
                      onClick={() => toggleExpand(citation.id)}
                      className="text-xs font-mono text-[var(--nous-sol)] hover:underline mb-2"
                    >
                      {isExpanded ? 'Hide' : 'Show'} Abstract
                    </button>
                    {isExpanded && (
                      <p className="text-xs font-mono text-[var(--nous-fg-3)] leading-relaxed">
                        {citation.abstract}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Virtualized rendering for large lists (100+ items)
  return (
    <div
      className={cn(
        'rounded-lg border border-[var(--nous-border-1)]',
        className
      )}
    >
      {/* List stats for large lists */}
      <div className="px-4 py-2 bg-[var(--nous-bg-3)] border-b border-[var(--nous-border-1)] flex items-center justify-between">
        <span className="text-xs font-mono text-[var(--nous-fg-3)]">
          {citations.length.toLocaleString()} citations
        </span>
        <span className="text-[10px] font-mono text-muted-foreground">
          Virtual scrolling enabled
        </span>
      </div>
      <List
        ref={listRef}
        height={height - 36} // Subtract header height
        width="100%"
        itemCount={citations.length}
        itemSize={180} // Fixed height per item for virtualization
        itemData={itemData}
        overscanCount={5}
        className="scrollbar-thin scrollbar-thumb-[var(--nous-border-1)] scrollbar-track-transparent"
      >
        {CitationItem}
      </List>
    </div>
  );
}
