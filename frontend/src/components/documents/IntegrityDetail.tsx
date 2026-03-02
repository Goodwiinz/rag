'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Loader2, RefreshCw, Shield } from 'lucide-react';
import { getIntegrityLevel } from '@/types/scispace';
import type { IntegrityLevel, IntegrityScoreResponse } from '@/types/scispace';
import {
  getIntegrityScore,
  triggerIntegrityCheck,
} from '@/services/scispaceService';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { APIErrorClass } from '@/types/api';

interface IntegrityDetailProps {
  documentId: string;
  isOpen: boolean;
  onClose: () => void;
}

const levelColors: Record<IntegrityLevel, string> = {
  human: '#00ff9f',
  mixed: '#ffb700',
  ai: '#ef4444',
};

const levelLabels: Record<IntegrityLevel, string> = {
  human: 'Likely Human',
  mixed: 'Mixed / Uncertain',
  ai: 'Likely AI-Generated',
};

export const IntegrityDetail: React.FC<IntegrityDetailProps> = ({
  documentId,
  isOpen,
  onClose,
}) => {
  const [score, setScore] = useState<IntegrityScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noScore, setNoScore] = useState(false);

  const fetchScore = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNoScore(false);

    try {
      const data = await getIntegrityScore(documentId);
      setScore(data);
    } catch (err) {
      if (err instanceof APIErrorClass && err.error.status_code === 404) {
        setNoScore(true);
      } else {
        setError('Failed to load integrity score.');
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    if (isOpen) {
      fetchScore();
    } else {
      setScore(null);
      setError(null);
      setNoScore(false);
    }
  }, [isOpen, fetchScore]);

  const handleRunCheck = async () => {
    setChecking(true);
    setError(null);

    try {
      await triggerIntegrityCheck(documentId);
      await fetchScore();
    } catch {
      setError('Integrity check failed. Please try again.');
    } finally {
      setChecking(false);
    }
  };

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderGauge = (aiProbability: number) => {
    const level = getIntegrityLevel(aiProbability);
    const color = levelColors[level];
    const pct = Math.round(aiProbability * 100);

    return (
      <div className="flex flex-col items-center gap-3">
        <div
          className="relative flex h-28 w-28 items-center justify-center rounded-full border-4"
          style={{ borderColor: color }}
        >
          <div className="flex flex-col items-center">
            <span className="text-3xl font-bold tabular-nums" style={{ color }}>
              {pct}%
            </span>
            <span className="text-[10px] uppercase tracking-wider text-gray-300">
              AI Prob.
            </span>
          </div>
        </div>
        <span className="text-sm font-medium" style={{ color }}>
          {levelLabels[level]}
        </span>
      </div>
    );
  };

  const renderSegmentBar = (aiProbability: number) => {
    const level = getIntegrityLevel(aiProbability);
    const color = levelColors[level];
    const pct = Math.round(aiProbability * 100);

    return (
      <div className="flex items-center gap-2">
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${pct}%`, backgroundColor: color }}
          />
        </div>
        <span
          className="w-10 text-right text-xs font-medium tabular-nums"
          style={{ color }}
        >
          {pct}%
        </span>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg border-[#1a1a1a] bg-black/30 backdrop-blur-xl sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-100">
            <Shield className="h-5 w-5 text-[#00d4ff]" />
            AI Integrity Analysis
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Detection analysis for this document
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {loading && (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <Loader2 className="h-8 w-8 animate-spin text-[#00d4ff]" />
              <span className="text-sm text-gray-400">Loading score...</span>
            </div>
          )}

          {error && !loading && (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-8">
              <AlertCircle className="h-8 w-8 text-red-400" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {noScore && !loading && !error && (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <Shield className="h-10 w-10 text-gray-500" />
              <p className="text-sm text-gray-400">
                No integrity score available yet.
              </p>
              <p className="text-xs text-gray-500">
                Run a check to analyze this document for AI-generated content.
              </p>
            </div>
          )}

          {score && !loading && (
            <>
              <div className="flex items-center justify-center">
                {renderGauge(score.ai_probability)}
              </div>

              <div className="grid grid-cols-2 gap-3 rounded-lg border border-[#1a1a1a] bg-black/20 p-4">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-gray-500">
                    Method
                  </span>
                  <p className="text-sm font-medium text-gray-300">
                    {score.method}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-gray-500">
                    Analyzed
                  </span>
                  <p className="text-sm font-medium text-gray-300">
                    {formatDate(score.analyzed_at)}
                  </p>
                </div>
              </div>

              {score.segment_scores.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Segment Breakdown
                  </h4>
                  <div className="max-h-60 space-y-3 overflow-y-auto pr-1">
                    {score.segment_scores.map((segment, idx) => {
                      return (
                        <div
                          key={idx}
                          className="rounded-md border border-[#1a1a1a] bg-black/20 p-3"
                        >
                          <p className="mb-2 line-clamp-2 text-xs text-gray-300">
                            {segment.text_preview}
                          </p>
                          {renderSegmentBar(segment.ai_probability)}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter className="border-t border-[#1a1a1a] pt-4">
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-gray-300 hover:text-white"
          >
            Close
          </Button>
          <Button
            onClick={handleRunCheck}
            disabled={checking || loading}
            className="gap-2 border border-[#00d4ff]/30 bg-[#00d4ff]/10 text-[#00d4ff] hover:bg-[#00d4ff]/20"
          >
            {checking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {checking ? 'Analyzing...' : 'Run New Check'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default IntegrityDetail;
