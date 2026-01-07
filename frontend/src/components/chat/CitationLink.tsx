'use client';

import { Badge } from '@/components/ui/badge';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import { Citation, getScoreColor, truncateText } from '@/utils/citationParser';
import { motion } from 'framer-motion';
import { ExternalLink, FileText, TrendingUp } from 'lucide-react';
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
 * Inline citation link component that renders as a clickable badge
 * Shows tooltip on hover with citation details
 */
export function CitationLink({
  citationNumber,
  citation,
  onClick,
  isActive = false,
  className,
}: CitationLinkProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (citation && onClick) {
      onClick(citation);
    }
  };

  // Score-based color (phosphor green for high, amber for medium, etc.)
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
            ? 'bg-primary/30 text-primary border-primary/50 shadow-[0_0_8px_rgba(0,255,159,0.3)]'
            : 'bg-primary/15 text-primary hover:bg-primary/25 hover:border-primary/30'
          : 'bg-muted/50 text-muted-foreground cursor-not-allowed',
        className
      )}
      aria-label={citation ? `Citation ${citationNumber}: ${citation.title}` : `Citation ${citationNumber}`}
    >
      [{citationNumber}]
    </motion.button>
  );

  // If no citation data, just render the button without hover card
  if (!citation) {
    return citationButton;
  }

  return (
    <HoverCard openDelay={200} closeDelay={100}>
      <HoverCardTrigger asChild>
        {citationButton}
      </HoverCardTrigger>
      <HoverCardContent
        align="start"
        side="top"
        className={cn(
          'w-80 p-0 overflow-hidden',
          'bg-card border border-primary/20',
          'shadow-[0_0_20px_rgba(0,255,159,0.1)]'
        )}
      >
        {/* Header */}
        <div className="px-3 py-2 bg-background border-b border-primary/10">
          <div className="flex items-start gap-2">
            <FileText className="w-4 h-4 mt-0.5 text-primary shrink-0" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-white truncate">
                {citation.title}
              </h4>
              {citation.source && (
                <p className="text-xs text-gray-500 truncate mt-0.5">
                  {citation.source}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Content preview */}
        {citation.content && (

          <div className="px-3 py-2 border-b border-primary/10">
            <p className="text-xs text-gray-400 leading-relaxed">
              {truncateText(citation.content, 200)}
            </p>
          </div>
        )}

        {/* Footer with score and action */}
        <div className="px-3 py-2 flex items-center justify-between bg-card/50">
          <div className="flex items-center gap-2">
            <TrendingUp className={cn('w-3 h-3', scoreColorClass)} />
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] px-1.5 py-0 h-5 border-0',
                scorePercent >= 80
                  ? 'bg-green-500/20 text-green-400'
                  : scorePercent >= 60
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : scorePercent >= 40
                      ? 'bg-orange-500/20 text-orange-400'
                      : 'bg-red-500/20 text-red-400'
              )}
            >
              {scorePercent}% match
            </Badge>
          </div>
          <button
            onClick={handleClick}
            className={cn(
              'flex items-center gap-1 text-xs',
              'text-primary/70 hover:text-primary',
              'transition-colors'
            )}
          >
            View <ExternalLink className="w-3 h-3" />
          </button>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

export default CitationLink;
