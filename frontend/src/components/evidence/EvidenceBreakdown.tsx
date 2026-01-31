'use client';

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, FileText, AlertTriangle } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useEvidenceBreakdown } from '@/hooks/useEvidenceMeter';
import { StanceBadge } from './StanceBadge';
import { ConfidenceBadge } from './ConfidenceIndicator';
import type { 
  EvidenceBreakdownProps, 
  StanceClassification, 
  Stance 
} from '@/types/evidence';

/** Group sources by stance */
function groupSourcesByStance(sources: StanceClassification[]) {
  const groups: Record<Exclude<Stance, 'not_addressed'>, StanceClassification[]> = {
    supporting: [],
    opposing: [],
    neutral: [],
  };
  
  sources.forEach(source => {
    if (source.stance !== 'not_addressed') {
      groups[source.stance].push(source);
    }
  });
  
  return groups;
}

/** Loading skeleton for breakdown panel */
function BreakdownSkeleton() {
  return (
    <div className="space-y-4" data-testid="breakdown-skeleton">
      {[1, 2, 3].map((i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <div className="space-y-2 pl-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Single source item in breakdown */
function SourceItem({
  source,
  onClick,
  index,
}: {
  source: StanceClassification;
  onClick?: (sourceId: string) => void;
  index: number;
}) {
  const handleClick = () => {
    if (onClick) {
      onClick(source.source_id);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ delay: index * 0.05 }}
      className={cn(
        'group rounded-lg border p-3 transition-colors',
        onClick 
          ? 'cursor-pointer hover:bg-accent hover:border-accent-foreground/20' 
          : '',
        source.is_retracted && 'opacity-60 border-dashed'
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={onClick ? 0 : undefined}
      role={onClick ? 'button' : undefined}
      aria-label={onClick ? `View source: ${source.title}` : undefined}
      data-testid={`source-item-${source.source_id}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <span 
            className="font-medium text-sm truncate" 
            title={source.title}
          >
            {source.title}
          </span>
        </div>
        
        <div className="flex items-center gap-2 flex-shrink-0">
          <ConfidenceBadge confidence={source.confidence} />
          {onClick && (
            <ExternalLink 
              className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" 
              aria-hidden="true"
            />
          )}
        </div>
      </div>
      
      {/* Excerpt */}
      {source.justification_excerpt && (
        <blockquote className="mt-2 border-l-2 border-muted pl-3 text-xs text-muted-foreground italic line-clamp-3">
          "{source.justification_excerpt}"
        </blockquote>
      )}
      
      {/* Retracted warning */}
      {source.is_retracted && (
        <div className="mt-2 flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
          <AlertTriangle className="h-3 w-3" />
          <span>This source has been retracted</span>
        </div>
      )}
    </motion.div>
  );
}

/** Section for a stance group */
function StanceSection({
  stance,
  sources,
  onSourceClick,
  defaultOpen = true,
}: {
  stance: Exclude<Stance, 'not_addressed'>;
  sources: StanceClassification[];
  onSourceClick?: (sourceId: string) => void;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  
  if (sources.length === 0) {
    return null;
  }
  
  const stanceLabels = {
    supporting: 'Supporting Sources',
    opposing: 'Opposing Sources',
    neutral: 'Neutral Sources',
  };
  
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between px-2 py-1 h-auto"
          aria-expanded={isOpen}
        >
          <div className="flex items-center gap-2">
            <StanceBadge stance={stance} size="sm" />
            <span className="text-sm text-muted-foreground">
              {stanceLabels[stance]} ({sources.length})
            </span>
          </div>
          <motion.span
            animate={{ rotate: isOpen ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="text-muted-foreground"
          >
            ▼
          </motion.span>
        </Button>
      </CollapsibleTrigger>
      
      <CollapsibleContent>
        <AnimatePresence mode="sync">
          <div className="space-y-2 pl-2 pt-2">
            {sources.map((source, index) => (
              <SourceItem
                key={source.source_id}
                source={source}
                onClick={onSourceClick}
                index={index}
              />
            ))}
          </div>
        </AnimatePresence>
      </CollapsibleContent>
    </Collapsible>
  );
}

/**
 * EvidenceBreakdown Component
 * 
 * Expandable panel showing sources grouped by their stance on the claim.
 * Each source displays title, confidence score, and justification excerpt.
 * Clicking a source navigates to its detail view.
 * 
 * @example
 * <EvidenceBreakdown 
 *   claimHash="abc123"
 *   claim="Vitamin D reduces COVID severity"
 *   sources={sources}
 *   onSourceClick={(id) => navigate(`/source/${id}`)}
 * />
 */
export function EvidenceBreakdown({
  claimHash,
  claim,
  sources: initialSources,
  onSourceClick,
  className,
}: EvidenceBreakdownProps) {
  // Fetch breakdown data if sources not provided
  const { 
    data, 
    isLoading, 
    error 
  } = useEvidenceBreakdown({
    claimHash,
    enabled: initialSources.length === 0,
  });
  
  // Use provided sources or fetched data
  const sources = initialSources.length > 0 
    ? initialSources 
    : (data?.sources ?? []);
  
  // Group sources by stance
  const groupedSources = useMemo(
    () => groupSourcesByStance(sources),
    [sources]
  );
  
  // Loading state
  if (isLoading && initialSources.length === 0) {
    return (
      <div className={cn('space-y-4', className)}>
        <BreakdownSkeleton />
      </div>
    );
  }
  
  // Error state
  if (error && initialSources.length === 0) {
    return (
      <div 
        className={cn('text-sm text-destructive', className)}
        role="alert"
        data-testid="breakdown-error"
      >
        Failed to load evidence breakdown
      </div>
    );
  }
  
  // Empty state
  if (sources.length === 0) {
    return (
      <div 
        className={cn(
          'flex items-center justify-center p-4 text-sm text-muted-foreground',
          className
        )}
        data-testid="breakdown-empty"
      >
        No source classifications available
      </div>
    );
  }
  
  const totalRelevant = 
    groupedSources.supporting.length + 
    groupedSources.opposing.length + 
    groupedSources.neutral.length;
  
  return (
    <div 
      className={cn('space-y-3', className)}
      data-testid="evidence-breakdown"
      role="region"
      aria-label={`Evidence breakdown for claim: ${claim}`}
    >
      {/* Summary */}
      <p className="text-xs text-muted-foreground">
        Showing {totalRelevant} sources that address this claim
      </p>
      
      {/* Stance sections */}
      <div className="space-y-2">
        <StanceSection
          stance="supporting"
          sources={groupedSources.supporting}
          onSourceClick={onSourceClick}
          defaultOpen={true}
        />
        
        <StanceSection
          stance="opposing"
          sources={groupedSources.opposing}
          onSourceClick={onSourceClick}
          defaultOpen={true}
        />
        
        <StanceSection
          stance="neutral"
          sources={groupedSources.neutral}
          onSourceClick={onSourceClick}
          defaultOpen={false}
        />
      </div>
    </div>
  );
}

export default EvidenceBreakdown;
