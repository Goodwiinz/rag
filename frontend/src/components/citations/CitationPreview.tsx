/**
 * CitationPreview Component
 * 
 * Renders clickable [Doc N] citation links with popover showing source details.
 */

import React, { useState } from 'react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { FileText, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface CitationPreviewProps {
  /** Citation index (e.g., 1 for [Doc 1]) */
  index: number;
  /** Document title */
  title: string;
  /** Document ID (for navigation) */
  documentId?: string;
  /** Relevance score (0-1) */
  score?: number;
  /** Content snippet */
  snippet?: string;
  /** Document type (optional) */
  documentType?: string;
  /** Custom className */
  className?: string;
  /** Callback when citation is clicked */
  onClick?: (documentId?: string) => void;
}

/**
 * CitationPreview Component
 * 
 * Displays an inline citation link [Doc N] that shows a popover with
 * document details when clicked or hovered.
 */
export const CitationPreview: React.FC<CitationPreviewProps> = ({
  index,
  title,
  documentId,
  score,
  snippet,
  documentType,
  className,
  onClick,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const relevancePercent = score ? Math.round(score * 100) : undefined;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (onClick && documentId) {
      onClick(documentId);
    }
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'inline-flex items-center gap-0.5 px-1 py-0.5 rounded text-xs font-medium',
            'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
            'hover:bg-blue-200 dark:hover:bg-blue-900/50',
            'transition-colors cursor-pointer',
            'border border-blue-300 dark:border-blue-700',
            className
          )}
          onClick={handleClick}
          aria-label={`Citation ${index}: ${title}`}
        >
          <FileText className="w-3 h-3" />
          <span>[Doc {index}]</span>
        </button>
      </PopoverTrigger>
      
      <PopoverContent className="w-96 p-4 shadow-lg" align="start">
        <div className="space-y-3">
          {/* Title */}
          <div>
            <div className="flex items-start justify-between gap-2">
              <h4 className="font-semibold text-sm line-clamp-2 flex-1">
                {title}
              </h4>
              {documentId && (
                <button
                  onClick={handleClick}
                  className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                  aria-label="View document"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Metadata badges */}
          <div className="flex flex-wrap gap-2">
            {relevancePercent !== undefined && (
              <Badge variant="secondary" className="text-xs">
                {relevancePercent}% relevant
              </Badge>
            )}
            {documentType && (
              <Badge variant="outline" className="text-xs">
                {documentType}
              </Badge>
            )}
            <Badge variant="outline" className="text-xs">
              Citation {index}
              </Badge>
          </div>

          {/* Snippet */}
          {snippet && (
            <div className="pt-2 border-t">
              <p className="text-xs text-muted-foreground line-clamp-4">
                {snippet}
              </p>
            </div>
          )}

          {/* View document hint */}
          {documentId && (
            <div className="pt-2 border-t">
              <p className="text-xs text-muted-foreground italic">
                Click the link or icon to view the full document
              </p>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default CitationPreview;
