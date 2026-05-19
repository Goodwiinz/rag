'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { IconButton } from "@/components/ui/icon-button";
import { cn } from '@/lib/utils';
import { THEME } from '@/theme/constants';
import {
  Citation,
  getScoreColor,
  getCitationIdentifier,
  isNavigableCitation,
} from '@/utils/citationParser';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  FileText,
  TrendingUp,
  X,
} from 'lucide-react';
import { useState } from 'react';

// Terminal Observatory theme colors
// Using THEME.colors instead of local constants

interface CitationPreviewProps {
  citation: Citation;
  isExpanded?: boolean;
  onToggle?: () => void;
  onClose?: () => void;
  onNavigate?: (citation: Citation) => void;
  className?: string;
}

/**
 * Expandable citation preview component
 * Shows full document content with expand/collapse animation
 * Terminal Observatory themed
 */
export function CitationPreview({
  citation,
  isExpanded = false,
  onToggle,
  onClose,
  onNavigate,
  className,
}: CitationPreviewProps) {
  const [copied, setCopied] = useState(false);

  const scorePercent = Math.round(citation.score * 100);
  const scoreColorClass = getScoreColor(citation.score);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(citation.content || citation.title);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleNavigate = () => {
    if (onNavigate) {
      onNavigate(citation);
    }
  };

  // Determine if this is an external source (no database document)
  const isExternal = !isNavigableCitation(citation);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        'rounded-lg overflow-hidden',
        'bg-card border border-border',
        'hover:border-primary/30 transition-colors',
        className
      )}
    >
      {/* Header - Always visible */}
      <div
        className={cn(
          'flex items-start gap-3 px-3 py-3',
          'cursor-pointer hover:bg-muted transition-colors'
        )}
        onClick={onToggle}
      >
        {/* Icon */}
        <div
          className={cn(
            'flex items-center justify-center w-8 h-8 rounded-md shrink-0 mt-0.5',
            'bg-primary/10 border border-primary/20'
          )}
        >
          <FileText
            className="w-4 h-4"
            style={{ color: THEME.colors.primary }}
          />
        </div>

        {/* Title and metadata */}
        <div className="flex-1 min-w-0">
          {/* Main title */}
          <h4
            className="text-sm font-medium leading-tight line-clamp-2"
            style={{ color: THEME.colors.primary }}
          >
            {citation.title}
          </h4>

          {/* Source type badge and score in same row */}
          <div className="flex items-center gap-2 mt-1.5">
            {citation.source && (
              <Badge
                variant="outline"
                className="text-[9px] px-1.5 py-0 h-4 bg-muted text-muted-foreground border-border"
              >
                {citation.source}
              </Badge>
            )}
            {isExternal && (
              <Badge
                variant="outline"
                className="text-[9px] px-1.5 py-0 h-4"
                style={{
                  backgroundColor: `${THEME.colors.accent}15`,
                  color: THEME.colors.accent,
                  borderColor: `${THEME.colors.accent}30`,
                }}
              >
                External
              </Badge>
            )}
          </div>
        </div>

        {/* Right side - score and controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Relevance score */}
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
            {scorePercent}%
          </Badge>

          {/* Expand/Collapse chevron */}
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-gray-500" />
          </motion.div>

          {/* Close button */}
          {onClose && (
            <IconButton
              label="Close preview"
              icon={<X className="w-4 h-4 text-muted-foreground hover:text-foreground" />}
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="p-1 rounded hover:bg-muted transition-colors"
            />
          )}
        </div>
      </div>

      {/* Expandable content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Content preview */}
            {citation.content && (
              <div className="px-3 py-3 border-t border-border">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span
                    className="text-[10px] font-mono uppercase tracking-wider"
                    style={{ color: `${THEME.colors.primary}80` }}
                  >
                    Content Preview
                  </span>
                  <IconButton
                    label="Copy citation content"
                    icon={
                      copied ? (
                        <Check
                          className="w-3 h-3"
                          style={{ color: THEME.colors.primary }}
                        />
                      ) : (
                        <Copy className="w-3 h-3 text-muted-foreground hover:text-foreground" />
                      )
                    }
                    onClick={handleCopy}
                    className="p-1 rounded hover:bg-muted transition-colors"
                  />
                </div>
                <div
                  className={cn(
                    'p-3 rounded-md',
                    'bg-background border border-border',
                    'max-h-48 overflow-y-auto',
                    'scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent'
                  )}
                >
                  <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap font-mono">
                    {citation.content}
                  </p>
                </div>
              </div>
            )}

            {/* Footer with ID and actions */}
            <div className="px-3 py-2.5 flex items-center justify-between border-t border-border bg-background">
              <div className="flex items-center gap-2 text-[10px] text-gray-600">
                <span className="font-mono">REF:</span>
                <code className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                  {getCitationIdentifier(citation).slice(0, 16)}
                </code>
              </div>

              {isNavigableCitation(citation) ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleNavigate}
                  className="h-6 text-[10px] px-2 hover:bg-primary/10"
                  style={{ color: THEME.colors.primary }}
                >
                  View Document
                  <ExternalLink className="w-3 h-3 ml-1" />
                </Button>
              ) : (
                <span
                  className="text-[10px] font-mono"
                  style={{ color: `${THEME.colors.accent}80` }}
                >
                  External source
                </span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default CitationPreview;
