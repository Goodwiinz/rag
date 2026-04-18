'use client';

/**
 * DraftComparison Component
 * Side-by-side comparison of two draft versions
 */

import React, { useMemo } from 'react';
import { ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { DraftComparison as DraftComparisonType } from '@/services/projectService';

export interface DraftComparisonProps {
  comparison: DraftComparisonType;
  draftA?: { content: string };
  draftB?: { content: string };
}

export const DraftComparison: React.FC<DraftComparisonProps> = ({
  comparison,
  draftA,
  draftB,
}) => {
  const diffView = useMemo(() => {
    if (!draftA || !draftB) {
      return null;
    }

    const linesA = draftA.content.split('\n');
    const linesB = draftB.content.split('\n');
    const normalizedA = new Set(linesA.map((line) => line.trim()).filter(Boolean));
    const normalizedB = new Set(linesB.map((line) => line.trim()).filter(Boolean));

    return {
      versionA: linesA.map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return { text: line, type: 'unchanged' as const };
        return normalizedB.has(trimmed)
          ? { text: line, type: 'unchanged' as const }
          : { text: line, type: 'removed' as const };
      }),
      versionB: linesB.map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return { text: line, type: 'unchanged' as const };
        return normalizedA.has(trimmed)
          ? { text: line, type: 'unchanged' as const }
          : { text: line, type: 'added' as const };
      }),
    };
  }, [draftA, draftB]);

  const getTrendIcon = (diff: number) => {
    if (diff > 0) return <TrendingUp className="h-4 w-4 text-[#00ff9f]" />;
    if (diff < 0) return <TrendingDown className="h-4 w-4 text-red-400" />;
    return <Minus className="h-4 w-4 text-gray-500" />;
  };

  const formatDiff = (diff: number) => {
    if (diff > 0) return `+${diff}`;
    return diff.toString();
  };

  const similarityColor =
    comparison.similarity_score > 0.8
      ? 'text-[#00ff9f]'
      : comparison.similarity_score > 0.5
      ? 'text-[#ffb700]'
      : 'text-red-400';

  const lineClass = (type: 'added' | 'removed' | 'unchanged') => {
    if (type === 'added') return 'bg-[#00ff9f]/10 text-[#8ef9d0]';
    if (type === 'removed') return 'bg-red-500/10 text-red-300';
    return 'text-gray-400';
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-[#1a1a1a]">
        <h3 className="font-mono font-bold text-gray-200">Version Comparison</h3>
      </div>

      {/* Stats Comparison */}
      <div className="grid grid-cols-3 gap-4 p-4 border-b border-[#1a1a1a]">
        {/* Version A */}
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase mb-2">
            Version {comparison.version_a.version}
          </div>
          <div className="space-y-2">
            <div className="p-2 bg-[#1a1a1a] rounded">
              <div className="text-lg font-mono text-gray-300">
                {comparison.version_a.word_count}
              </div>
              <div className="text-xs text-gray-500">words</div>
            </div>
            <div className="p-2 bg-[#1a1a1a] rounded">
              <div className="text-lg font-mono text-gray-300">
                {comparison.version_a.citation_count}
              </div>
              <div className="text-xs text-gray-500">citations</div>
            </div>
          </div>
          <div className="text-xs text-gray-500 font-mono mt-2">
            {new Date(comparison.version_a.created_at).toLocaleDateString()}
          </div>
        </div>

        {/* Comparison Arrow & Stats */}
        <div className="flex flex-col items-center justify-center">
          <ArrowRight className="h-6 w-6 text-gray-500 mb-4" />

          <div className="space-y-3 w-full">
            <div className="flex items-center justify-center gap-2">
              {getTrendIcon(comparison.word_count_diff)}
              <span className="text-sm font-mono text-gray-300">
                {formatDiff(comparison.word_count_diff)} words
              </span>
            </div>
            <div className="flex items-center justify-center gap-2">
              {getTrendIcon(comparison.citation_count_diff)}
              <span className="text-sm font-mono text-gray-300">
                {formatDiff(comparison.citation_count_diff)} citations
              </span>
            </div>
            <div className="p-2 bg-[#1a1a1a] rounded text-center">
              <div className={`text-lg font-mono ${similarityColor}`}>
                {(comparison.similarity_score * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500">similarity</div>
            </div>
          </div>
        </div>

        {/* Version B */}
        <div className="text-center">
          <div className="text-xs text-gray-500 font-mono uppercase mb-2">
            Version {comparison.version_b.version}
          </div>
          <div className="space-y-2">
            <div className="p-2 bg-[#1a1a1a] rounded">
              <div className="text-lg font-mono text-gray-300">
                {comparison.version_b.word_count}
              </div>
              <div className="text-xs text-gray-500">words</div>
            </div>
            <div className="p-2 bg-[#1a1a1a] rounded">
              <div className="text-lg font-mono text-gray-300">
                {comparison.version_b.citation_count}
              </div>
              <div className="text-xs text-gray-500">citations</div>
            </div>
          </div>
          <div className="text-xs text-gray-500 font-mono mt-2">
            {new Date(comparison.version_b.created_at).toLocaleDateString()}
          </div>
        </div>
      </div>

      {/* Side-by-side Content (if provided) */}
      {diffView && (
        <div className="grid grid-cols-2 divide-x divide-[#1a1a1a]">
          <div className="p-4 max-h-[400px] overflow-y-auto">
            <div className="text-xs text-gray-500 font-mono uppercase mb-2">
              Version {comparison.version_a.version}
            </div>
            <div className="text-sm font-mono whitespace-pre-wrap space-y-1">
              {diffView.versionA.map((line, idx) => (
                <div key={`a-${idx}`} className={`px-1.5 py-0.5 rounded ${lineClass(line.type)}`}>
                  {line.text || ' '}
                </div>
              ))}
            </div>
          </div>
          <div className="p-4 max-h-[400px] overflow-y-auto">
            <div className="text-xs text-gray-500 font-mono uppercase mb-2">
              Version {comparison.version_b.version}
            </div>
            <div className="text-sm font-mono whitespace-pre-wrap space-y-1">
              {diffView.versionB.map((line, idx) => (
                <div key={`b-${idx}`} className={`px-1.5 py-0.5 rounded ${lineClass(line.type)}`}>
                  {line.text || ' '}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DraftComparison;
