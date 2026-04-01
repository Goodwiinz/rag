'use client';

import React, { useMemo } from 'react';
import { Check, X, Quote } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ToneOption } from '@/types/scispace';

interface RewriteDiffViewProps {
  original: string;
  rewritten: string;
  toneApplied: ToneOption;
  citationsPreserved: string[];
  onAccept: (rewritten: string) => void;
  onReject: () => void;
}

type DiffEntry = { type: 'same' | 'removed' | 'added'; word: string };

function computeWordDiff(original: string, rewritten: string): DiffEntry[] {
  const origWords = original.split(/\s+/).filter(Boolean);
  const newWords = rewritten.split(/\s+/).filter(Boolean);
  const m = origWords.length;
  const n = newWords.length;

  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    Array(n + 1).fill(0)
  );

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (origWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const result: DiffEntry[] = [];
  let i = m;
  let j = n;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origWords[i - 1] === newWords[j - 1]) {
      result.push({ type: 'same', word: origWords[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'added', word: newWords[j - 1] });
      j--;
    } else {
      result.push({ type: 'removed', word: origWords[i - 1] });
      i--;
    }
  }

  return result.reverse();
}

const toneConfig: Record<
  ToneOption,
  { label: string; color: string; bg: string }
> = {
  academic: {
    label: 'Academic',
    color: 'text-brand-cyan',
    bg: 'bg-brand-cyan/10 border-brand-cyan/30',
  },
  simplified: {
    label: 'Simplified',
    color: 'text-helios',
    bg: 'bg-helios/10 border-helios/30',
  },
  concise: {
    label: 'Concise',
    color: 'text-sol',
    bg: 'bg-sol/10 border-sol/30',
  },
  expanded: {
    label: 'Expanded',
    color: 'text-purple-400',
    bg: 'bg-purple-400/10 border-purple-400/30',
  },
};

export const RewriteDiffView: React.FC<RewriteDiffViewProps> = ({
  original,
  rewritten,
  toneApplied,
  citationsPreserved,
  onAccept,
  onReject,
}) => {
  const diff = useMemo(
    () => computeWordDiff(original, rewritten),
    [original, rewritten]
  );

  const originalDiff = useMemo(
    () =>
      diff.filter((entry) => entry.type === 'same' || entry.type === 'removed'),
    [diff]
  );

  const rewrittenDiff = useMemo(
    () =>
      diff.filter((entry) => entry.type === 'same' || entry.type === 'added'),
    [diff]
  );

  const tone = toneConfig[toneApplied];

  return (
    <div className="overflow-hidden rounded-lg border border-[#1a1a1a] bg-[#0a0a0a]">
      <div className="flex items-center justify-between border-b border-[#1a1a1a] px-4 py-3">
        <div className="flex items-center gap-3">
          <h3 className="font-mono text-sm font-bold text-gray-200">
            Tone Rewrite
          </h3>
          <Badge className={cn('border text-xs', tone.bg, tone.color)}>
            {tone.label}
          </Badge>
        </div>
        {citationsPreserved.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Quote className="h-3 w-3" />
            <span>
              {citationsPreserved.length} citation
              {citationsPreserved.length !== 1 ? 's' : ''} preserved
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 divide-y divide-[#1a1a1a] md:grid-cols-2 md:divide-x md:divide-y-0">
        <div className="flex flex-col">
          <div className="border-b border-[#1a1a1a] px-4 py-2">
            <span className="font-mono text-xs uppercase text-gray-500">
              Original
            </span>
          </div>
          <div className="max-h-[400px] overflow-y-auto p-4">
            <p className="text-sm leading-relaxed">
              {originalDiff.map((entry, idx) => (
                <span
                  key={idx}
                  className={cn(
                    entry.type === 'removed' &&
                      'rounded-sm bg-red-500/20 px-0.5 text-red-300 line-through'
                  )}
                >
                  {entry.word}{' '}
                </span>
              ))}
            </p>
          </div>
        </div>

        <div className="flex flex-col">
          <div className="border-b border-[#1a1a1a] px-4 py-2">
            <span className="font-mono text-xs uppercase text-gray-500">
              Rewritten
            </span>
          </div>
          <div className="max-h-[400px] overflow-y-auto p-4">
            <p className="text-sm leading-relaxed">
              {rewrittenDiff.map((entry, idx) => (
                <span
                  key={idx}
                  className={cn(
                    entry.type === 'added' &&
                      'rounded-sm bg-sol/20 px-0.5 text-[#8ef9d0]'
                  )}
                >
                  {entry.word}{' '}
                </span>
              ))}
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-[#1a1a1a] px-4 py-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-gray-400 hover:bg-[#1a1a1a] hover:text-gray-200"
          onClick={onReject}
          aria-label="Reject rewrite"
        >
          <X className="h-3.5 w-3.5" />
          Reject
        </Button>
        <Button
          size="sm"
          className="gap-1.5 bg-sol/10 text-sol hover:bg-sol/20"
          onClick={() => onAccept(rewritten)}
          aria-label="Accept rewrite"
        >
          <Check className="h-3.5 w-3.5" />
          Accept
        </Button>
      </div>
    </div>
  );
};

export default RewriteDiffView;
