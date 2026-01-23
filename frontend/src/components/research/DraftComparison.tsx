'use client';

/**
 * DraftComparison Component
 * Side-by-side comparison of two draft versions
 */

import React from 'react';
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
      {draftA && draftB && (
        <div className="grid grid-cols-2 divide-x divide-[#1a1a1a]">
          <div className="p-4 max-h-[400px] overflow-y-auto">
            <div className="text-xs text-gray-500 font-mono uppercase mb-2">
              Version {comparison.version_a.version}
            </div>
            <div className="text-sm font-mono text-gray-400 whitespace-pre-wrap">
              {draftA.content}
            </div>
          </div>
          <div className="p-4 max-h-[400px] overflow-y-auto">
            <div className="text-xs text-gray-500 font-mono uppercase mb-2">
              Version {comparison.version_b.version}
            </div>
            <div className="text-sm font-mono text-gray-400 whitespace-pre-wrap">
              {draftB.content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DraftComparison;
