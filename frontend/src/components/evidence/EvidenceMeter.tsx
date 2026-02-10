'use client';

import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { 
  useEvidenceMeter, 
  getConsensusText, 
  getConsensusColor, 
  getConsensusEmoji 
} from '@/hooks/useEvidenceMeter';
import type { 
  EvidenceMeterProps, 
  EvidenceMeterData, 
  MeterSegment 
} from '@/types/evidence';
import { EvidenceBreakdown } from './EvidenceBreakdown';
import { ConfidenceIndicator } from './ConfidenceIndicator';

/** Colors for each stance type */
const STANCE_COLORS = {
  supporting: 'bg-green-500',
  opposing: 'bg-red-500',
  neutral: 'bg-gray-400',
} as const;

/**
 * Calculate meter segments from evidence data
 */
function calculateSegments(data: EvidenceMeterData): MeterSegment[] {
  const { supporting, opposing, neutral } = data;
  const total = supporting + opposing + neutral;
  
  if (total === 0) return [];
  
  const segments: MeterSegment[] = [];
  
  if (supporting > 0) {
    segments.push({
      stance: 'supporting',
      count: supporting,
      percentage: (supporting / total) * 100,
      color: STANCE_COLORS.supporting,
    });
  }
  
  if (neutral > 0) {
    segments.push({
      stance: 'neutral',
      count: neutral,
      percentage: (neutral / total) * 100,
      color: STANCE_COLORS.neutral,
    });
  }
  
  if (opposing > 0) {
    segments.push({
      stance: 'opposing',
      count: opposing,
      percentage: (opposing / total) * 100,
      color: STANCE_COLORS.opposing,
    });
  }
  
  return segments;
}

/**
 * Loading skeleton for the evidence meter
 */
export function EvidenceMeterSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('space-y-2', className)} data-testid="evidence-meter-skeleton">
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-4 rounded-full" />
        <Skeleton className="h-4 w-40" />
      </div>
      <Skeleton className="h-3 w-full rounded-full" />
    </div>
  );
}

/**
 * Empty state when no sources are found
 */
export function EvidenceMeterEmpty({ className }: { className?: string }) {
  return (
    <div 
      className={cn(
        'flex items-center gap-2 text-sm text-muted-foreground',
        className
      )}
      data-testid="evidence-meter-empty"
    >
      <AlertTriangle className="h-4 w-4" />
      <span>No sources found for this claim</span>
    </div>
  );
}

/**
 * Animated meter bar with colored segments
 */
function MeterBar({ 
  segments, 
  ariaLabel 
}: { 
  segments: MeterSegment[];
  ariaLabel: string;
}) {
  if (segments.length === 0) {
    return (
      <div 
        className="h-3 w-full rounded-full bg-muted"
        role="meter"
        aria-label={ariaLabel}
        aria-valuenow={0}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    );
  }
  
  return (
    <div 
      className="relative h-3 w-full overflow-hidden rounded-full bg-muted"
      role="meter"
      aria-label={ariaLabel}
      aria-valuenow={segments.find(s => s.stance === 'supporting')?.percentage ?? 0}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="flex h-full">
        <AnimatePresence mode="wait">
          {segments.map((segment, index) => (
            <motion.div
              key={segment.stance}
              initial={{ width: 0 }}
              animate={{ width: `${segment.percentage}%` }}
              exit={{ width: 0 }}
              transition={{ 
                duration: 0.5, 
                delay: index * 0.1,
                ease: 'easeOut'
              }}
              className={cn('h-full', segment.color)}
              title={`${segment.stance}: ${segment.count} (${segment.percentage.toFixed(0)}%)`}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

/**
 * Evidence Agreement Meter Component
 * 
 * Displays a visual indicator showing consensus level across retrieved sources
 * for a research claim. Features color-coded segments (green for supporting,
 * red for opposing, gray for neutral) with accessible labels.
 */
export function EvidenceMeter({
  claim,
  sourceIds,
  queryId,
  className,
  onSourceClick,
}: EvidenceMeterProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const { 
    data, 
    isLoading, 
    error 
  } = useEvidenceMeter({ claim, sourceIds, queryId });
  
  // Calculate meter segments
  const segments = useMemo(() => {
    if (!data) return [];
    return calculateSegments(data);
  }, [data]);

  // Generate accessible description
  const ariaLabel = useMemo(() => {
    if (!data) return 'Loading evidence meter';
    const text = getConsensusText(data);
    return `Evidence meter: ${text}. ${data.supporting} supporting, ${data.opposing} opposing, ${data.neutral} neutral out of ${data.total_sources} sources.`;
  }, [data]);
  
  // Handle loading state
  if (isLoading) {
    return <EvidenceMeterSkeleton className={className} />;
  }
  
  // Handle error state
  if (error) {
    return (
      <div 
        className={cn('text-sm text-destructive', className)}
        role="alert"
        data-testid="evidence-meter-error"
      >
        Failed to load evidence meter
      </div>
    );
  }
  
  // Handle no data or empty sources
  if (!data || data.total_sources === 0) {
    return <EvidenceMeterEmpty className={className} />;
  }
  
  const consensusText = getConsensusText(data);
  const consensusColor = getConsensusColor(data.consensus_level);
  const consensusEmoji = getConsensusEmoji(data.consensus_level);
  const showConfidenceWarning = data.average_confidence < 0.85;
  
  return (
    <div 
      className={cn('space-y-2', className)}
      data-testid="evidence-meter"
    >
      {/* Header with consensus text */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span 
            className="text-base" 
            role="img" 
            aria-hidden="true"
          >
            {consensusEmoji}
          </span>
          <span className={cn('text-sm font-medium', consensusColor)}>
            {consensusText}
          </span>
          {showConfidenceWarning && (
            <ConfidenceIndicator 
              confidence={data.average_confidence} 
              className="ml-1"
            />
          )}
        </div>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="h-6 px-2"
          aria-expanded={isExpanded}
          aria-controls="evidence-breakdown"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              <span className="sr-only">Collapse breakdown</span>
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              <span className="sr-only">Expand breakdown</span>
            </>
          )}
        </Button>
      </div>
      
      {/* Animated meter bar */}
      <MeterBar segments={segments} ariaLabel={ariaLabel} />
      
      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className={cn('h-2 w-2 rounded-full', STANCE_COLORS.supporting)} />
          <span>Supporting ({data.supporting})</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={cn('h-2 w-2 rounded-full', STANCE_COLORS.neutral)} />
          <span>Neutral ({data.neutral})</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={cn('h-2 w-2 rounded-full', STANCE_COLORS.opposing)} />
          <span>Opposing ({data.opposing})</span>
        </div>
      </div>
      
      {/* Expandable breakdown panel */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            id="evidence-breakdown"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <EvidenceBreakdown
              claimHash={data.claim_hash}
              claim={data.claim}
              sources={[]} // Will be fetched by the component
              onSourceClick={onSourceClick}
              className="mt-3 border-t pt-3"
            />
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Retracted sources warning */}
      {data.retracted_sources > 0 && (
        <div 
          className="flex items-center gap-2 rounded-md bg-yellow-50 dark:bg-yellow-900/20 p-2 text-xs text-yellow-700 dark:text-yellow-400"
          role="alert"
        >
          <AlertTriangle className="h-3 w-3" />
          <span>
            ⚠️ {data.retracted_sources} retracted source{data.retracted_sources > 1 ? 's' : ''} found (excluded from count)
          </span>
        </div>
      )}
    </div>
  );
}

export default EvidenceMeter;
