'use client';

import { Badge } from '@/components/ui/badge';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import { Citation, getScoreColor, truncateText, isNavigableCitation } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { ExternalLink, FileText, TrendingUp, Archive } from 'lucide-react';
import React from 'react';

// Terminal Observatory theme colors
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

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
  const scoreColorClass = citation ? getScoreColor(citation.score) : 'text-gray-400';

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
            ? 'bg-[#00ff9f]/30 text-[#00ff9f] border-[#00ff9f]/50 shadow-[0_0_8px_rgba(0,255,159,0.3)]'
            : canNavigate
              ? 'bg-[#00ff9f]/15 text-[#00ff9f] hover:bg-[#00ff9f]/25 hover:border-[#00ff9f]/30 cursor-pointer'
              : 'bg-[#ffb700]/15 text-[#ffb700] hover:bg-[#ffb700]/25 hover:border-[#ffb700]/30 cursor-default'
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
          'w-[340px] p-0 overflow-hidden',
          'bg-[#0a0a0a] border border-[#1a1a1a]',
          'shadow-[0_0_30px_rgba(0,255,159,0.08)]'
        )}
      >
        {/* Header with title */}
        <div
          className="px-3 py-3 border-b border-[#1a1a1a]"
          style={{ backgroundColor: '#080808' }}
        >
          <div className="flex items-start gap-3">
            {/* Icon */}
            <div className={cn(
              'flex items-center justify-center w-8 h-8 rounded-md shrink-0',
              canNavigate
                ? 'bg-[#00ff9f]/10 border border-[#00ff9f]/20'
                : 'bg-[#ffb700]/10 border border-[#ffb700]/20'
            )}>
              {canNavigate ? (
                <FileText className="w-4 h-4" style={{ color: PHOSPHOR_GREEN }} />
              ) : (
                <Archive className="w-4 h-4" style={{ color: AMBER }} />
              )}
            </div>

            {/* Title and metadata */}
            <div className="flex-1 min-w-0">
              <h4
                className="text-sm font-medium leading-tight line-clamp-2"
                style={{ color: canNavigate ? PHOSPHOR_GREEN : AMBER }}
              >
                {citation.title}
              </h4>

              {/* Source type and external ID */}
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                {citation.source && (
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1.5 py-0 h-4 bg-[#1a1a1a] text-gray-400 border-[#2a2a2a]"
                  >
                    {citation.source}
                  </Badge>
                )}
                {!canNavigate && (
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1.5 py-0 h-4"
                    style={{
                      backgroundColor: `${AMBER}15`,
                      color: AMBER,
                      borderColor: `${AMBER}30`
                    }}
                  >
                    External
                  </Badge>
                )}
              </div>

              {/* External reference ID */}
              {citation.externalReferenceId && !canNavigate && (
                <p className="text-[10px] text-gray-500 truncate mt-1.5 font-mono">
                  REF: {citation.externalReferenceId}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Content preview */}
        {citation.content && (
          <div className="px-3 py-3 border-b border-[#1a1a1a]">
            <div
              className="text-[10px] font-mono uppercase tracking-wider mb-2"
              style={{ color: `${PHOSPHOR_GREEN}60` }}
            >
              Preview
            </div>
            <p className="text-xs text-gray-400 leading-relaxed font-mono">
              {truncateText(citation.content, 180)}
            </p>
          </div>
        )}

        {/* Footer with score and action */}
        <div
          className="px-3 py-2.5 flex items-center justify-between"
          style={{ backgroundColor: '#050505' }}
        >
          {/* Relevance score */}
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] px-2 py-0.5 border-0',
                scorePercent >= 80
                  ? 'bg-green-500/20 text-green-400'
                  : scorePercent >= 60
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : scorePercent >= 40
                      ? 'bg-orange-500/20 text-orange-400'
                      : 'bg-red-500/20 text-red-400'
              )}
            >
              <TrendingUp className={cn('w-3 h-3 mr-1', scoreColorClass)} />
              {scorePercent}% match
            </Badge>
          </div>

          {/* Action */}
          {canNavigate ? (
            <button
              onClick={handleClick}
              className="flex items-center gap-1 text-[10px] font-mono transition-colors hover:opacity-80"
              style={{ color: PHOSPHOR_GREEN }}
            >
              View Document
              <ExternalLink className="w-3 h-3" />
            </button>
          ) : (
            <span
              className="text-[10px] font-mono"
              style={{ color: `${AMBER}80` }}
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
