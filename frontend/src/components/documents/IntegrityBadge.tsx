'use client';

import React from 'react';
import { Shield, ShieldQuestion } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getIntegrityLevel } from '@/types/scispace';
import type { IntegrityLevel } from '@/types/scispace';
import { Button } from '@/components/ui/button';

interface IntegrityBadgeProps {
  documentId: string;
  score?: { ai_probability: number; human_probability: number } | null;
  onRequestCheck?: () => void;
  compact?: boolean;
}

const levelColors: Record<
  IntegrityLevel,
  { bg: string; text: string; border: string }
> = {
  human: {
    bg: 'bg-sol/10',
    text: 'text-sol',
    border: 'border-sol/30',
  },
  mixed: {
    bg: 'bg-helios/10',
    text: 'text-helios',
    border: 'border-helios/30',
  },
  ai: {
    bg: 'bg-red-500/10',
    text: 'text-red-400',
    border: 'border-red-500/30',
  },
};

const levelLabels: Record<IntegrityLevel, string> = {
  human: 'Likely human',
  mixed: 'Mixed/uncertain',
  ai: 'Likely AI-generated',
};

export const IntegrityBadge: React.FC<IntegrityBadgeProps> = ({
  documentId: _documentId,
  score,
  onRequestCheck,
  compact = false,
}) => {
  if (!score) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={onRequestCheck}
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-white"
        aria-label="Check AI integrity"
      >
        <ShieldQuestion className="h-3.5 w-3.5" />
        {!compact && <span>Check</span>}
      </Button>
    );
  }

  const level = getIntegrityLevel(score.ai_probability);
  const colors = levelColors[level];
  const isAiDominant = score.ai_probability >= 0.5;
  const dominantPct = Math.round(
    (isAiDominant ? score.ai_probability : score.human_probability) * 100
  );
  const dominantLabel = isAiDominant ? 'AI' : 'Human';

  if (compact) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold',
          colors.bg,
          colors.text,
          colors.border
        )}
        title={levelLabels[level]}
      >
        <Shield className="h-3 w-3" />
        {dominantPct}%
      </span>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        colors.bg,
        colors.text,
        colors.border
      )}
      title={levelLabels[level]}
    >
      <Shield className="h-3.5 w-3.5" />
      {dominantLabel}: {dominantPct}%
    </span>
  );
};

export default IntegrityBadge;
