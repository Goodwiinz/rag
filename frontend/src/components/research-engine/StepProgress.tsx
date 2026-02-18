'use client';

import { useState } from 'react';
import {
  Check,
  X,
  Loader2,
  Clock,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Zap,
  Compass,
} from 'lucide-react';

export interface StepData {
  stepIndex: number;
  stepName: string;
  stepType: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  mode?: 'deterministic' | 'exploratory';
  tokenCount: number;
  qualityMarks: Array<{
    check_type: string;
    passed: boolean;
    details?: string;
  }>;
  output?: string;
  sources?: string[];
  prompt?: string;
  errorMessage?: string;
}

interface StepProgressProps {
  step: StepData;
}

export function StepProgress({ step }: StepProgressProps) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon = () => {
    switch (step.status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-gray-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-[#00d4ff]" />;
      case 'complete':
        return <Check className="h-4 w-4 text-[#00ff9f]" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-400" />;
    }
  };

  const statusColor = () => {
    switch (step.status) {
      case 'pending':
        return 'border-gray-700';
      case 'running':
        return 'border-[#00d4ff]/50';
      case 'complete':
        return 'border-[#00ff9f]/50';
      case 'error':
        return 'border-red-500/50';
    }
  };

  return (
    <div
      className={`border ${statusColor()} rounded bg-black/30 transition-colors`}
    >
      {/* Header row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/5 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-gray-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-500 shrink-0" />
        )}

        {statusIcon()}

        <span className="font-mono text-sm text-gray-200 flex-1 truncate">
          <span className="text-gray-500 mr-2">#{step.stepIndex + 1}</span>
          {step.stepName}
        </span>

        {/* Type badge */}
        <span className="px-2 py-0.5 text-xs font-mono rounded bg-white/5 text-gray-400 border border-white/10">
          {step.stepType}
        </span>

        {/* Mode badge */}
        {step.mode && (
          <span
            className={`flex items-center gap-1 px-2 py-0.5 text-xs font-mono rounded border ${
              step.mode === 'deterministic'
                ? 'bg-[#00ff9f]/10 text-[#00ff9f] border-[#00ff9f]/20'
                : 'bg-[#ffb700]/10 text-[#ffb700] border-[#ffb700]/20'
            }`}
          >
            {step.mode === 'deterministic' ? (
              <Zap className="h-3 w-3" />
            ) : (
              <Compass className="h-3 w-3" />
            )}
            {step.mode === 'deterministic' ? 'Deterministic' : 'Exploratory'}
          </span>
        )}

        {/* Quality marks */}
        {step.status === 'complete' && step.qualityMarks.length > 0 && (
          <div className="flex items-center gap-1">
            {step.qualityMarks.map((mark, i) => (
              <span
                key={i}
                title={`${mark.check_type}: ${mark.passed ? 'passed' : 'failed'}${mark.details ? ` - ${mark.details}` : ''}`}
              >
                {mark.passed ? (
                  <Check className="h-3.5 w-3.5 text-[#00ff9f]" />
                ) : (
                  <X className="h-3.5 w-3.5 text-red-400" />
                )}
              </span>
            ))}
          </div>
        )}

        {/* Token count */}
        {step.tokenCount > 0 && (
          <span className="text-xs font-mono text-gray-500">
            {step.tokenCount.toLocaleString()} tok
          </span>
        )}
      </button>

      {/* Expandable details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/5">
          {/* Error message */}
          {step.errorMessage && (
            <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded">
              <p className="text-xs font-mono text-red-400">
                {step.errorMessage}
              </p>
            </div>
          )}

          {/* Output preview */}
          {step.output && (
            <div className="mt-3">
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-wide mb-1">
                Output
              </h4>
              <div className="p-3 bg-black/40 rounded border border-white/5 max-h-40 overflow-auto">
                <p className="text-xs font-mono text-gray-300 whitespace-pre-wrap">
                  {step.output.length > 500
                    ? step.output.slice(0, 500) + '...'
                    : step.output}
                </p>
              </div>
            </div>
          )}

          {/* Sources used */}
          {step.sources && step.sources.length > 0 && (
            <div>
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-wide mb-1">
                Sources
              </h4>
              <div className="flex flex-wrap gap-1">
                {step.sources.map((source, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-xs font-mono bg-[#ffb700]/10 text-[#ffb700] rounded border border-[#ffb700]/20"
                  >
                    {source}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Prompt (collapsible) */}
          {step.prompt && <PromptSection prompt={step.prompt} />}

          {/* Quality check details */}
          {step.qualityMarks.length > 0 && (
            <div>
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-wide mb-1">
                Quality Checks
              </h4>
              <div className="space-y-1">
                {step.qualityMarks.map((mark, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs font-mono"
                  >
                    {mark.passed ? (
                      <Check className="h-3 w-3 text-[#00ff9f]" />
                    ) : (
                      <X className="h-3 w-3 text-red-400" />
                    )}
                    <span className="text-gray-400">{mark.check_type}</span>
                    {mark.details && (
                      <span className="text-gray-600">- {mark.details}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PromptSection({ prompt }: { prompt: string }) {
  const [showPrompt, setShowPrompt] = useState(false);

  return (
    <div>
      <button
        onClick={() => setShowPrompt(!showPrompt)}
        className="flex items-center gap-1 text-xs font-mono text-gray-500 uppercase tracking-wide hover:text-gray-400 transition-colors"
      >
        {showPrompt ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        Prompt
      </button>
      {showPrompt && (
        <div className="mt-1 p-3 bg-black/40 rounded border border-white/5 max-h-60 overflow-auto">
          <pre className="text-xs font-mono text-gray-400 whitespace-pre-wrap">
            {prompt}
          </pre>
        </div>
      )}
    </div>
  );
}
