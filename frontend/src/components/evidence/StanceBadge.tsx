'use client';

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import type { StanceBadgeProps, Stance } from '@/types/evidence';

/**
 * Stance badge variants using class-variance-authority
 * Green for supporting, red for opposing, gray for neutral
 */
const stanceBadgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      stance: {
        supporting: 
          'border-transparent bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50',
        opposing: 
          'border-transparent bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50',
        neutral: 
          'border-transparent bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700',
        not_addressed:
          'border-transparent bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700',
      },
      size: {
        sm: 'text-xs',
        md: 'text-xs',
        lg: 'text-sm',
      },
    },
    defaultVariants: {
      stance: 'neutral',
      size: 'md',
    },
  }
);

/**
 * Get human-readable label for stance
 */
function getStanceLabel(stance: Stance): string {
  switch (stance) {
    case 'supporting':
      return 'Supporting';
    case 'opposing':
      return 'Opposing';
    case 'neutral':
      return 'Neutral';
    case 'not_addressed':
      return 'Not Addressed';
    default:
      return 'Unknown';
  }
}

/**
 * Get emoji indicator for stance
 */
function getStanceEmoji(stance: Stance): string {
  switch (stance) {
    case 'supporting':
      return '✓';
    case 'opposing':
      return '✗';
    case 'neutral':
      return '–';
    case 'not_addressed':
      return '?';
    default:
      return '';
  }
}

/**
 * StanceBadge Component
 * 
 * Color-coded pill badge indicating source stance on a claim.
 * Shows confidence percentage when below 85% threshold.
 * 
 * @example
 * <StanceBadge stance="supporting" />
 * <StanceBadge stance="opposing" confidence={0.72} showConfidence />
 */
export function StanceBadge({
  stance,
  confidence,
  showConfidence = false,
  size = 'md',
  className,
}: StanceBadgeProps) {
  const label = getStanceLabel(stance);
  const emoji = getStanceEmoji(stance);
  const showConfidenceValue = showConfidence && confidence !== undefined && confidence < 0.85;
  const confidencePercent = confidence !== undefined ? Math.round(confidence * 100) : null;
  
  return (
    <span
      className={cn(stanceBadgeVariants({ stance, size }), className)}
      data-testid={`stance-badge-${stance}`}
      role="status"
      aria-label={`Stance: ${label}${confidencePercent !== null && showConfidenceValue ? `, Confidence: ${confidencePercent}%` : ''}`}
    >
      <span className="mr-1" aria-hidden="true">{emoji}</span>
      <span>{label}</span>
      {showConfidenceValue && confidencePercent !== null && (
        <span className="ml-1 opacity-75">
          ({confidencePercent}%)
        </span>
      )}
    </span>
  );
}

export default StanceBadge;
export { stanceBadgeVariants };
