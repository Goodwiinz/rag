'use client';

/**
 * DraftGenerationProgress Component
 * Shows real-time progress of draft generation
 */

import React, { useEffect, useState } from 'react';
import { Loader2, XCircle, CheckCircle, AlertCircle } from 'lucide-react';
import type { GenerationStatus } from '@/services/projectService';

export interface DraftGenerationProgressProps {
  status: GenerationStatus;
  onCancel?: () => void;
  onComplete?: (draftId: string) => void;
}

const statusSteps = [
  { key: 'pending', label: 'Initializing' },
  { key: 'analyzing', label: 'Analyzing Documents' },
  { key: 'generating', label: 'Generating Content' },
  { key: 'citing', label: 'Adding Citations' },
  { key: 'finalizing', label: 'Finalizing Draft' },
  { key: 'completed', label: 'Complete' },
];

export const DraftGenerationProgress: React.FC<
  DraftGenerationProgressProps
> = ({ status, onCancel, onComplete }) => {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status.status === 'completed' && status.draft_id && onComplete) {
      onComplete(status.draft_id);
    }
  }, [status.status, status.draft_id, onComplete]);

  useEffect(() => {
    if (
      status.started_at &&
      !['completed', 'failed', 'cancelled'].includes(status.status)
    ) {
      const startTime = new Date(status.started_at).getTime();
      const interval = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [status.started_at, status.status]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getCurrentStepIndex = () => {
    return statusSteps.findIndex((s) => s.key === status.status);
  };

  const isCompleted = status.status === 'completed';
  const isFailed = status.status === 'failed';
  const isCancelled = status.status === 'cancelled';
  const isRunning = !isCompleted && !isFailed && !isCancelled;

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {isRunning && (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          )}
          {isCompleted && <CheckCircle className="h-5 w-5 text-primary" />}
          {isFailed && <AlertCircle className="h-5 w-5 text-red-400" />}
          {isCancelled && <XCircle className="h-5 w-5 text-muted-foreground" />}
          <div>
            <h3 className="font-mono font-medium text-foreground">
              {isCompleted
                ? 'Draft Generated'
                : isFailed
                  ? 'Generation Failed'
                  : isCancelled
                    ? 'Generation Cancelled'
                    : 'Generating Draft'}
            </h3>
            <p className="text-xs text-muted-foreground font-mono">
              {status.current_step}
            </p>
          </div>
        </div>

        {isRunning && onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs font-mono text-muted-foreground hover:text-red-400 border border-border rounded hover:border-red-400/50 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground font-mono">
            Progress
          </span>
          <span className="text-xs text-primary font-mono">
            {status.progress}%
          </span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              isFailed
                ? 'bg-red-500'
                : isCancelled
                  ? 'bg-muted-foreground'
                  : 'bg-gradient-to-r from-primary to-primary/60'
            }`}
            style={{ width: `${status.progress}%` }}
          />
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-2 mb-4">
        {statusSteps.slice(0, -1).map((step, idx) => {
          const currentIdx = getCurrentStepIndex();
          const isActive = idx === currentIdx;
          const isDone = idx < currentIdx || isCompleted;

          return (
            <div
              key={step.key}
              className={`flex items-center gap-3 text-sm font-mono ${
                isActive
                  ? 'text-primary'
                  : isDone
                    ? 'text-muted-foreground'
                    : 'text-muted-foreground/40'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center ${
                  isActive
                    ? 'bg-primary/20 border border-primary'
                    : isDone
                      ? 'bg-primary/10'
                      : 'bg-muted'
                }`}
              >
                {isDone && <CheckCircle className="w-3 h-3 text-primary" />}
                {isActive && (
                  <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                )}
              </div>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>

      {/* Time Info */}
      <div className="flex items-center justify-between text-xs text-muted-foreground font-mono pt-4 border-t border-border">
        <span>Elapsed: {formatTime(elapsed)}</span>
        {status.duration && isCompleted && (
          <span>Completed in {status.duration.toFixed(1)}s</span>
        )}
      </div>
    </div>
  );
};

export default DraftGenerationProgress;
