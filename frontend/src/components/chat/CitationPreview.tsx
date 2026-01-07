'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  ChevronUp,
  FileText,
  ExternalLink,
  TrendingUp,
  Copy,
  Check,
  X,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Citation, getScoreColor } from '@/utils/citationParser';

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

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        'rounded-lg overflow-hidden',
        'bg-[#0a0a0a] border border-[#00ff9f]/20',
        'shadow-[0_0_15px_rgba(0,255,159,0.08)]',
        className
      )}
    >
      {/* Header - Always visible */}
      <div
        className={cn(
          'flex items-center justify-between gap-3 px-4 py-3',
          'bg-[#0f0f0f] border-b border-[#00ff9f]/10',
          'cursor-pointer hover:bg-[#141414] transition-colors'
        )}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className={cn(
            'flex items-center justify-center w-8 h-8 rounded-md',
            'bg-[#00ff9f]/10 border border-[#00ff9f]/20'
          )}>
            <FileText className="w-4 h-4 text-[#00ff9f]" />
          </div>

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

        <div className="flex items-center gap-2">
          {/* Relevance score badge */}
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

          {/* Expand/Collapse button */}
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-gray-400" />
          </motion.div>

          {/* Close button */}
          {onClose && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="p-1 rounded hover:bg-gray-800 transition-colors"
            >
              <X className="w-4 h-4 text-gray-500 hover:text-gray-300" />
            </button>
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
              <div className="px-4 py-3 border-b border-[#00ff9f]/10">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs text-[#00ff9f]/60 font-mono">
                    CONTENT
                  </span>
                  <button
                    onClick={handleCopy}
                    className="p-1 rounded hover:bg-gray-800 transition-colors"
                    title="Copy content"
                  >
                    {copied ? (
                      <Check className="w-3 h-3 text-[#00ff9f]" />
                    ) : (
                      <Copy className="w-3 h-3 text-gray-500 hover:text-gray-300" />
                    )}
                  </button>
                </div>
                <div className={cn(
                  'p-3 rounded-md',
                  'bg-[#080808] border border-[#1a1a1a]',
                  'max-h-48 overflow-y-auto',
                  'scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent'
                )}>
                  <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {citation.content}
                  </p>
                </div>
              </div>
            )}

            {/* Footer with actions */}
            <div className="px-4 py-3 flex items-center justify-between bg-[#080808]">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className="font-mono">ID:</span>
                <code className="px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-400">
                  {citation.documentId.slice(0, 12)}...
                </code>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleNavigate}
                className={cn(
                  'h-7 text-xs',
                  'text-[#00ff9f]/70 hover:text-[#00ff9f]',
                  'hover:bg-[#00ff9f]/10'
                )}
              >
                View Full Document
                <ExternalLink className="w-3 h-3 ml-1.5" />
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default CitationPreview;
