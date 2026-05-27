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
        'inline-grid place-items-center align-text-top mx-[2px]',
        'h-[18px] min-w-[18px] px-[5px] rounded-full',
        'font-nous-ui text-[10px] font-semibold leading-none',
        'transition-all duration-150 cursor-pointer',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40',
        citation
          ? isActive
            ? 'bg-[var(--nous-sol)] text-white shadow-[0_0_0_2px_rgba(212,160,57,0.18)]'
            : canNavigate
              ? 'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] hover:bg-[var(--nous-sol)] hover:text-white hover:-translate-y-px dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)] dark:hover:bg-[var(--nous-helios)] dark:hover:text-[var(--nous-nyx)]'
              : 'bg-transparent border border-[var(--nous-border-1)] text-[var(--nous-fg-3)] cursor-default'
          : 'bg-[var(--nous-bg-2)] text-[var(--nous-fg-3)] cursor-not-allowed opacity-60',
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
          'bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]',
          'shadow-[0_8px_24px_rgba(10,10,14,0.10)] dark:shadow-[0_8px_24px_rgba(0,0,0,0.45)]'
        )}
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
          <div className="flex items-start gap-2.5">
            <div
              className={cn(
                'flex items-center justify-center w-7 h-7 rounded shrink-0 mt-0.5',
                canNavigate
                  ? 'bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] border border-[rgba(212,160,57,0.25)]'
                  : 'bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]'
              )}
            >
              {canNavigate ? (
                <FileText className="w-3.5 h-3.5 text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)]" />
              ) : (
                <Archive className="w-3.5 h-3.5 text-[var(--nous-fg-3)]" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <h4
                className="text-[13px] font-medium leading-snug line-clamp-2 text-[var(--nous-fg-1)]"
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
                    className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--nous-bg-1)] text-[var(--nous-fg-2)] border border-[var(--nous-border-1)]"
                    style={{ fontFamily: 'var(--nous-font-mono)' }}
                  >
                    {citation.source}
                  </span>
                )}

                {!canNavigate && (
                  <span
                    className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--nous-bg-1)] text-[var(--nous-fg-3)] border border-[var(--nous-border-1)]"
                    style={{ fontFamily: 'var(--nous-font-mono)' }}
                  >
                    External
                  </span>
                )}
              </div>

              {citation.externalReferenceId && !canNavigate && (
                <p
                  className="text-[9px] text-[var(--nous-fg-3)] mt-1 truncate"
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
          <div className="px-3 py-2.5 border-b border-[var(--nous-border-1)]">
            <div className="flex items-center gap-1.5 mb-1.5">
              <BookOpen className="w-3 h-3 text-[var(--nous-sol)]/60" />
              <span
                className="text-[9px] uppercase tracking-wider text-[var(--nous-fg-3)]"
                style={{ fontFamily: 'var(--nous-font-mono)' }}
              >
                Preview
              </span>
            </div>
            <p
              className="text-[11px] text-[var(--nous-fg-2)] leading-relaxed line-clamp-3"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              {truncateText(previewContent, 200)}
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="px-3 py-2 bg-[var(--nous-bg-2)] flex items-center justify-end">
          {canNavigate ? (
            <button
              onClick={handleClick}
              className="flex items-center gap-1.5 text-[10px] text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)] hover:opacity-80 transition-opacity"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              View Document
              <ExternalLink className="w-3 h-3" />
            </button>
          ) : (
            <span
              className="text-[10px] text-[var(--nous-fg-3)]"
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
