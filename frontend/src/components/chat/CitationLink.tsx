'use client';

import {
    HoverCard,
    HoverCardContent,
    HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import { Citation, isNavigableCitation, truncateText } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { Archive, BookOpen, ExternalLink, FileText, TrendingUp } from 'lucide-react';
import React from 'react';

interface CitationLinkProps {
  /** The citation number (1-based, matches [Doc N]) */
  citationNumber: number;
  /** The citation data */
  citation?: Citation;
  /** Click handler - navigates to document detail */
  onClick?: (citation: Citation) => void;
  /** Whether the citation is currently selected/active */
  isActive?: boolean;
  /** Custom class names */
  className?: string;
}

/**
 * Clean up content by removing metadata prefixes if present
 */
function cleanContentPreview(content: string): string {
  // Remove common metadata patterns that might be in the content
  const cleaned = content
    .replace(/^Title:\s*[^\n]+\n?/i, '')
    .replace(/^Authors?:\s*[^\n]+\n?/i, '')
    .replace(/^Categories?:\s*[^\n]+\n?/i, '')
    .replace(/^Abstract:\s*/i, '')
    .trim();

  return cleaned || content;
}

/**
 * Inline citation link component that renders as a clickable badge
 * Shows tooltip on hover with citation details
 * Terminal Observatory themed
 */
export function CitationLink({
  citationNumber,
  citation,
  onClick,
  isActive = false,
  className,
}: CitationLinkProps) {
  // Only allow navigation for citations with database document references
  const canNavigate = citation && isNavigableCitation(citation);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only call onClick if citation has a navigable document_id
    if (canNavigate && onClick) {
      onClick(citation);
    }
  };

  // Score-based color
  const scorePercent = citation ? Math.round(citation.score * 100) : 0;

  const citationButton = (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={handleClick}
      disabled={!citation}
      className={cn(
        'inline-flex items-center justify-center',
        'px-1.5 py-0.5 mx-0.5',
        'rounded text-[10px] font-mono font-medium',
        'transition-all duration-200',
        'border border-transparent',
        // Terminal Observatory theme colors
        citation
          ? isActive
            ? 'bg-primary/30 text-primary border-primary/50 shadow-[0_0_8px_rgba(212,160,57,0.3)]'
            : canNavigate
              ? 'bg-primary/15 text-primary hover:bg-primary/25 hover:border-primary/30 cursor-pointer'
              : 'bg-accent/15 text-accent hover:bg-accent/25 hover:border-accent/30 cursor-default'
          : 'bg-[#1a1a1a] text-gray-500 cursor-not-allowed',
        className
      )}
      aria-label={citation ? `Citation ${citationNumber}: ${citation.title}${!canNavigate ? ' (external reference)' : ''}` : `Citation ${citationNumber}`}
    >
      [{citationNumber}]
    </motion.button>
  );

  // If no citation data, just render the button without hover card
  if (!citation) {
    return citationButton;
  }

  // Get score color for badge
  const getScoreBadgeClass = (score: number) => {
    if (score >= 0.8) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (score >= 0.6) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    if (score >= 0.4) return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    return 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  // Clean content for preview
  const previewContent = citation.content ? cleanContentPreview(citation.content) : null;

  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>
        {citationButton}
      </HoverCardTrigger>
      <HoverCardContent
        align="start"
        side="top"
        sideOffset={8}
        className={cn(
          'w-[320px] p-0 overflow-hidden z-50',
          'bg-[#0a0a0a] border border-[#222]',
          'shadow-[0_4px_24px_rgba(0,0,0,0.5)]'
        )}
      >
        {/* Compact Header */}
        <div className="px-3 py-2.5 border-b border-[#1a1a1a] bg-[#080808]">
          <div className="flex items-start gap-2.5">
            {/* Icon */}
            <div className={cn(
              'flex items-center justify-center w-7 h-7 rounded shrink-0 mt-0.5',
              canNavigate
                ? 'bg-[#D4A039]/10 border border-[#D4A039]/20'
                : 'bg-[#ffb700]/10 border border-[#ffb700]/20'
            )}>
              {canNavigate ? (
                <FileText className="w-3.5 h-3.5 text-[#D4A039]" />
              ) : (
                <Archive className="w-3.5 h-3.5 text-[#ffb700]" />
              )}
            </div>

            {/* Title and badges */}
            <div className="flex-1 min-w-0">
              <h4
                className="text-[13px] font-medium leading-snug line-clamp-2"
                style={{ color: canNavigate ? '#D4A039' : '#ffb700' }}
              >
                {citation.title}
              </h4>

              {/* Badges row */}
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                {/* Score badge */}
                <span className={cn(
                  'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono border',
                  getScoreBadgeClass(citation.score)
                )}>
                  <TrendingUp className="w-2.5 h-2.5" />
                  {scorePercent}%
                </span>

                {/* Source type */}
                {citation.source && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[#1a1a1a] text-gray-500 border border-[#2a2a2a]">
                    {citation.source}
                  </span>
                )}

                {/* External badge */}
                {!canNavigate && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/20">
                    External
                  </span>
                )}
              </div>

              {/* External reference ID */}
              {citation.externalReferenceId && !canNavigate && (
                <p className="text-[9px] text-gray-600 mt-1 font-mono truncate">
                  REF: {citation.externalReferenceId}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Content preview - only if we have meaningful content */}
        {previewContent && previewContent.length > 10 && (
          <div className="px-3 py-2.5 border-b border-[#1a1a1a]">
            <div className="flex items-center gap-1.5 mb-1.5">
              <BookOpen className="w-3 h-3 text-[#D4A039]/50" />
              <span className="text-[9px] font-mono uppercase tracking-wider text-[#D4A039]/50">
                Preview
              </span>
            </div>
            <p className="text-[11px] text-gray-400 leading-relaxed line-clamp-3">
              {truncateText(previewContent, 200)}
            </p>
          </div>
        )}

        {/* Footer action */}
        <div className="px-3 py-2 bg-[#050505] flex items-center justify-end">
          {canNavigate ? (
            <button
              onClick={handleClick}
              className="flex items-center gap-1.5 text-[10px] font-mono text-[#D4A039] hover:text-[#D4A039]/80 transition-colors"
            >
              View Document
              <ExternalLink className="w-3 h-3" />
            </button>
          ) : (
            <span className="text-[10px] font-mono text-[#ffb700]/60">
              External source
            </span>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

export default CitationLink;
