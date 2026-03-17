'use client';

import React from 'react';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { FileText, ExternalLink, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { truncateText } from '@/utils/citationParser';
import type { AgentCitation } from '@/types/agent-chat';

interface AgentCitationBadgeProps {
  citationNumber: number;
  citation?: AgentCitation;
}

function getScoreBgClass(score: number): string {
  if (score >= 0.8)
    return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400';
  if (score >= 0.6)
    return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400';
  if (score >= 0.4)
    return 'bg-orange-500/10 text-orange-600 dark:text-orange-400';
  return 'bg-red-500/10 text-red-600 dark:text-red-400';
}

export function AgentCitationBadge({
  citationNumber,
  citation,
}: AgentCitationBadgeProps) {
  const badge = (
    <button
      className={cn(
        'inline-flex items-center justify-center',
        'px-1.5 py-0.5 mx-0.5',
        'rounded text-[10px] font-mono font-medium',
        'transition-colors duration-150',
        citation
          ? 'bg-primary/10 text-primary hover:bg-primary/20 cursor-pointer'
          : 'bg-muted text-muted-foreground cursor-default'
      )}
      aria-label={
        citation
          ? `Citation ${citationNumber}: ${citation.documentTitle}`
          : `Citation ${citationNumber}`
      }
    >
      [{citationNumber}]
    </button>
  );

  if (!citation) return badge;

  const scorePercent = Math.round((citation.score ?? 0) * 100);
  const previewContent = citation.snippet
    ? truncateText(citation.snippet, 150)
    : null;

  return (
    <HoverCard openDelay={150} closeDelay={100}>
      <HoverCardTrigger asChild>{badge}</HoverCardTrigger>
      <HoverCardContent
        align="start"
        side="top"
        sideOffset={8}
        className="w-[280px] p-0 overflow-hidden z-50"
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-border">
          <div className="flex items-start gap-2">
            <div className="flex items-center justify-center w-6 h-6 rounded bg-primary/10 shrink-0 mt-0.5">
              <FileText className="w-3 h-3 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-xs font-medium text-foreground leading-snug line-clamp-2">
                {citation.documentTitle}
              </h4>
              <div className="flex items-center gap-1.5 mt-1">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono',
                    getScoreBgClass(citation.score ?? 0)
                  )}
                >
                  <TrendingUp className="w-2.5 h-2.5" />
                  {scorePercent}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Content preview */}
        {previewContent && (
          <div className="px-3 py-2 border-b border-border">
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
              {previewContent}
            </p>
          </div>
        )}

        {/* Footer */}
        {citation.documentId && (
          <div className="px-3 py-1.5 flex items-center justify-end">
            <a
              href={`/documents/${citation.documentId}`}
              className="flex items-center gap-1 text-[10px] font-medium text-primary hover:text-primary/80 transition-colors"
            >
              View Document
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}
