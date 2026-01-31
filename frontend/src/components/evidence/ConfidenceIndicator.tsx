'use client';

import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ConfidenceIndicatorProps } from '@/types/evidence';

/**
 * Get color class based on confidence level
 */
function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) {
    return 'text-green-500 dark:text-green-400';
  }
  if (confidence >= 0.70) {
    return 'text-yellow-500 dark:text-yellow-400';
  }
  return 'text-red-500 dark:text-red-400';
}

/**
 * Get confidence level description
 */
function getConfidenceDescription(confidence: number): string {
  const percent = Math.round(confidence * 100);
  
  if (confidence >= 0.85) {
    return `High confidence (${percent}%) - Classification is reliable.`;
  }
  if (confidence >= 0.70) {
    return `Moderate confidence (${percent}%) - Manual verification recommended.`;
  }
  return `Low confidence (${percent}%) - Classification may be inaccurate. Please verify manually.`;
}

/**
 * ConfidenceIndicator Component
 * 
 * Shows a warning indicator when classification confidence is below threshold.
 * Provides tooltip with confidence percentage and guidance.
 * 
 * @example
 * <ConfidenceIndicator confidence={0.72} />
 * <ConfidenceIndicator confidence={0.95} /> // Hidden when above threshold
 */
export function ConfidenceIndicator({
  confidence,
  threshold = 0.85,
  className,
}: ConfidenceIndicatorProps) {
  // Don't show indicator if confidence is above threshold
  if (confidence >= threshold) {
    return null;
  }
  
  const percent = Math.round(confidence * 100);
  const colorClass = getConfidenceColor(confidence);
  const description = getConfidenceDescription(confidence);
  const Icon = confidence < 0.70 ? AlertTriangle : Info;
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs cursor-help',
              colorClass,
              className
            )}
            data-testid="confidence-indicator"
            role="status"
            aria-label={`Classification confidence: ${percent}%`}
          >
            <Icon className="h-3 w-3" aria-hidden="true" />
            <span className="font-medium">{percent}%</span>
          </span>
        </TooltipTrigger>
        <TooltipContent 
          side="top" 
          className="max-w-xs"
          role="tooltip"
        >
          <p className="text-sm">{description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * Inline confidence badge for use in lists
 */
export function ConfidenceBadge({
  confidence,
  className,
}: {
  confidence: number;
  className?: string;
}) {
  const percent = Math.round(confidence * 100);
  const colorClass = getConfidenceColor(confidence);
  
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium',
        confidence >= 0.85 
          ? 'bg-green-50 dark:bg-green-900/20' 
          : confidence >= 0.70 
            ? 'bg-yellow-50 dark:bg-yellow-900/20'
            : 'bg-red-50 dark:bg-red-900/20',
        colorClass,
        className
      )}
      data-testid="confidence-badge"
      aria-label={`Confidence: ${percent}%`}
    >
      {percent}%
    </span>
  );
}

export default ConfidenceIndicator;
