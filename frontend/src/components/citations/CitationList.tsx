'use client';

import { useState } from 'react';
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
}

/**
 * CitationList Component
 *
 * Displays a list of research citations with Terminal Observatory theme.
 *
 * Features:
 * - Citation metadata display (title, authors, year, venue)
 * - "Needs review" badges for incomplete metadata
 * - Edit button for manual correction
 * - ArXiv ID and DOI badges
 * - Source attribution (arxiv, semantic_scholar, crossref)
 * - Scrollable list with max height
 */
export function CitationList({
  citations,
  onEdit,
  onDelete,
  className,
  showActions = true,
  maxHeight = '600px',
}: CitationListProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpand = (citationId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(citationId)) {
        next.delete(citationId);
      } else {
        next.add(citationId);
      }
      return next;
    });
  };

  const getSourceBadgeColor = (source?: string) => {
    switch (source) {
      case 'arxiv':
        return 'bg-[#00ff9f]/10 text-[#00ff9f] border-[#00ff9f]/20';
      case 'semantic_scholar':
        return 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20';
      case 'crossref':
        return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
      default:
        return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
    }
  };

  if (citations.length === 0) {
    return (
      <div className={cn('text-center py-12 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]', className)}>
        <BookOpen className="w-12 h-12 text-gray-600 mx-auto mb-4" />
        <p className="font-mono text-sm text-[var(--terminal-text-muted)]">No citations found</p>
        <p className="font-mono text-xs text-gray-600 mt-2">
          Citations will appear here after extraction
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)} style={{ maxHeight, overflowY: 'auto' }}>
      {citations.map((citation) => {
        const isExpanded = expandedIds.has(citation.id);
        const hasAbstract = citation.abstract && citation.abstract.trim().length > 0;

        return (
          <div
            key={citation.id}
            className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] transition-all"
          >
            {/* Main Citation Info */}
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  {/* Title */}
                  <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)] line-clamp-2 mb-2">
                    {citation.documentTitle || 'Untitled'}
                  </h3>

                  {/* Authors and Year */}
                  <p className="text-xs font-mono text-[var(--terminal-text-muted)]">
                    {citation.authors && citation.authors.length > 0
                      ? citation.authors.slice(0, 3).join(', ') +
                        (citation.authors.length > 3 ? ', et al.' : '')
                      : 'Unknown authors'}
                    {citation.year && ` (${citation.year})`}
                  </p>

                  {/* Venue */}
                  {citation.venue && (
                    <p className="text-xs font-mono text-gray-500 mt-1">{citation.venue}</p>
                  )}
                </div>

                {/* Status Badges */}
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  {citation.needsReview && (
                    <span className="px-2 py-1 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-[var(--amber-gold)]/10 text-[var(--amber-gold)] border border-[var(--amber-gold)]/20 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Needs Review
                    </span>
                  )}

                  {showActions && onEdit && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(citation)}
                      className="h-7 px-2 text-xs font-mono text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)]"
                    >
                      <Edit className="w-3.5 h-3.5 mr-1" />
                      Edit
                    </Button>
                  )}
                </div>
              </div>

              {/* Identifiers (ArXiv, DOI) */}
              {(citation.arxivId || citation.doi) && (
                <div className="mt-3 pt-3 border-t border-[var(--terminal-border)] flex flex-wrap gap-2">
                  {citation.arxivId && (
                    <a
                      href={`https://arxiv.org/abs/${citation.arxivId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--phosphor-green)]/5 text-[var(--phosphor-green)] border border-[var(--phosphor-green)]/20 hover:bg-[var(--phosphor-green)]/10 transition-all flex items-center gap-1"
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
                <div className="mt-3 pt-3 border-t border-[var(--terminal-border)]">
                  <button
                    onClick={() => toggleExpand(citation.id)}
                    className="text-xs font-mono text-[var(--phosphor-green)] hover:underline mb-2"
                  >
                    {isExpanded ? 'Hide' : 'Show'} Abstract
                  </button>
                  {isExpanded && (
                    <p className="text-xs font-mono text-[var(--terminal-text-muted)] leading-relaxed">
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
