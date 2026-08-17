'use client';

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import {
  Citation,
  isNavigableCitation,
  truncateText,
} from '@/utils/citationParser';
import {
  Archive,
  BookOpen,
  ExternalLink,
  FileText,
  TrendingUp,
} from 'lucide-react';
import React from 'react';

interface CitationLinkProps {
  citationNumber: number;
  citation?: Citation;
  onClick?: (citation: Citation) => void;
  isActive?: boolean;
  className?: string;
}

function cleanContentPreview(content: string): string {
  const cleaned = content
    .replace(/^Title:\s*[^\n]+\n?/i, '')
    .replace(/^Authors?:\s*[^\n]+\n?/i, '')
    .replace(/^Categories?:\s*[^\n]+\n?/i, '')
    .replace(/^Abstract:\s*/i, '')
    .trim();

  return cleaned || content;
}

export function CitationLink({
  citationNumber,
  citation,
  onClick,
  isActive = false,
  className,
}: CitationLinkProps) {
  const canNavigate = citation && isNavigableCitation(citation);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (canNavigate && onClick) {
      onClick(citation);
    }
  };

  const scorePercent = citation ? Math.round(citation.score * 100) : 0;

  const citationButton = (
    <button
      type="button"
      onClick={handleClick}
      disabled={!citation}
      aria-label={
        citation
          ? `Citation ${citationNumber}: ${citation.title}${
              !canNavigate ? ' (external reference)' : ''
            }`
          : `Citation ${citationNumber}`
      }
      className={cn(
        // A dense synthesis paragraph can carry ten of these. The marker
        // therefore rests as a quiet ink wash and only commits to full
        // contrast once it is the one being read — a filled chip per
        // reference speckles the manuscript column.
        'inline-grid place-items-center align-middle mx-0.5 translate-y-[-2px]',
        'h-4 min-w-4 px-1 rounded-[5px]',
        'font-nous-mono text-[10px] font-medium tabular-nums leading-none',
        'transition-colors duration-150',
        'focus:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40',
        citation
          ? isActive
            ? 'bg-foreground text-background cursor-pointer'
            : canNavigate
              ? 'bg-foreground/[0.06] text-foreground/45 hover:text-foreground/90 cursor-pointer'
              : 'border border-(--nous-border-1) text-(--nous-fg-3) cursor-default'
          : 'bg-foreground/[0.06] text-foreground/30 cursor-not-allowed',
        className
      )}
    >
      {citationNumber}
    </button>
  );

  if (!citation) {
    return citationButton;
  }

  const getScoreBadgeClass = (score: number) => {
    if (score >= 0.8)
      return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30';
    if (score >= 0.6)
      return 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30';
    if (score >= 0.4)
      return 'bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/30';
    return 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30';
  };

  const previewContent = citation.content
    ? cleanContentPreview(citation.content)
    : null;

  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>{citationButton}</HoverCardTrigger>
      <HoverCardContent
        align="start"
        side="top"
        sideOffset={8}
        className={cn(
          'w-[320px] p-0 overflow-hidden z-50',
          'bg-(--nous-bg-1) border border-(--nous-border-1)',
          'shadow-[0_8px_24px_rgba(var(--nous-erebus-rgb),0.10)] dark:shadow-[0_8px_24px_rgba(0,0,0,0.45)]'
        )}
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-(--nous-border-1) bg-(--nous-bg-2)">
          <div className="flex items-start gap-2.5">
            <div
              className={cn(
                'flex items-center justify-center w-7 h-7 rounded shrink-0 mt-0.5',
                canNavigate
                  ? 'bg-(--nous-aurum) dark:bg-(--nous-ember) border border-[rgba(var(--nous-sol-rgb),0.25)]'
                  : 'bg-(--nous-bg-1) border border-(--nous-border-1)'
              )}
            >
              {canNavigate ? (
                <FileText className="w-3.5 h-3.5 text-(--nous-sol-safe) dark:text-(--nous-helios)" />
              ) : (
                <Archive className="w-3.5 h-3.5 text-(--nous-fg-3)" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <h4
                className="text-[13px] font-medium leading-snug line-clamp-2 text-(--nous-fg-1)"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                {citation.title}
              </h4>

              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono border',
                    getScoreBadgeClass(citation.score)
                  )}
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  <TrendingUp className="w-2.5 h-2.5" />
                  {scorePercent}%
                </span>

                {citation.source && (
                  <span
                    className="px-1.5 py-0.5 rounded text-[9px] bg-(--nous-bg-1) text-(--nous-fg-2) border border-(--nous-border-1)"
                    style={{ fontFamily: 'var(--nous-font-mono)' }}
                  >
                    {citation.source}
                  </span>
                )}

                {!canNavigate && (
                  <span
                    className="px-1.5 py-0.5 rounded text-[9px] bg-(--nous-bg-1) text-(--nous-fg-3) border border-(--nous-border-1)"
                    style={{ fontFamily: 'var(--nous-font-mono)' }}
                  >
                    External
                  </span>
                )}
              </div>

              {citation.externalReferenceId && !canNavigate && (
                <p
                  className="text-[9px] text-(--nous-fg-3) mt-1 truncate"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  REF: {citation.externalReferenceId}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Preview */}
        {previewContent && previewContent.length > 10 && (
          <div className="px-3 py-2.5 border-b border-(--nous-border-1)">
            <div className="flex items-center gap-1.5 mb-1.5">
              <BookOpen
                aria-hidden
                className="w-3 h-3 text-(--nous-fg-3)"
                strokeWidth={1.8}
              />
              <span
                className="text-[11px] font-medium text-(--nous-fg-3)"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Preview
              </span>
            </div>
            <p
              className="text-[12px] text-(--nous-fg-2) leading-relaxed line-clamp-4"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              {truncateText(previewContent, 240)}
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="px-3 py-2 bg-(--nous-bg-2) flex items-center justify-end">
          {canNavigate ? (
            <button
              onClick={handleClick}
              className="flex items-center gap-1.5 text-[10px] text-(--nous-sol-safe) dark:text-(--nous-helios) hover:opacity-80 transition-opacity"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              View Document
              <ExternalLink className="w-3 h-3" />
            </button>
          ) : (
            <span
              className="text-[10px] text-(--nous-fg-3)"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              External source
            </span>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

export default CitationLink;
