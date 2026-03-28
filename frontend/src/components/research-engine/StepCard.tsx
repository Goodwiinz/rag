'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ArrowUp,
  ArrowDown,
  Trash2,
  Search,
  FileText,
  Brain,
  Layers,
  Filter,
  Zap,
} from 'lucide-react';
import type { BlueprintStepDef } from '@/services/researchEngineService';

const STEP_TYPE_ICONS: Record<string, React.ReactNode> = {
  search: <Search className="h-4 w-4" />,
  extract: <FileText className="h-4 w-4" />,
  analyze: <Brain className="h-4 w-4" />,
  synthesize: <Layers className="h-4 w-4" />,
  filter: <Filter className="h-4 w-4" />,
};

const MODEL_OPTIONS = [
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet' },
  { value: 'claude-haiku-4-20250414', label: 'Claude Haiku' },
];

export interface StepCardProps {
  step: BlueprintStepDef;
  index: number;
  totalSteps: number;
  onChange: (updated: BlueprintStepDef) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
}

export function StepCard({
  step,
  index,
  totalSteps,
  onChange,
  onMoveUp,
  onMoveDown,
  onRemove,
}: StepCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [paramsText, setParamsText] = useState(
    JSON.stringify(step.parameters, null, 2)
  );
  const [paramsError, setParamsError] = useState<string | null>(null);

  const icon = STEP_TYPE_ICONS[step.type] || <Zap className="h-4 w-4" />;

  const modeColor =
    step.mode === 'deterministic'
      ? 'bg-[#D4A039]/10 text-[#D4A039] border-[#D4A039]/30'
      : 'bg-[#ffb700]/10 text-[#ffb700] border-[#ffb700]/30';

  const handleParamsChange = (value: string) => {
    setParamsText(value);
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      setParamsError(null);
      onChange({ ...step, parameters: parsed });
    } catch {
      setParamsError('Invalid JSON');
    }
  };

  const handleModeToggle = () => {
    const newMode =
      step.mode === 'deterministic' ? 'exploratory' : 'deterministic';
    const updates: Partial<BlueprintStepDef> = { mode: newMode };
    if (newMode === 'deterministic') {
      updates.temperature = undefined;
    }
    onChange({ ...step, ...updates });
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-3 p-3 cursor-pointer hover:bg-[#111] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="flex items-center justify-center w-7 h-7 rounded bg-[#1a1a1a] text-xs font-mono text-gray-400 shrink-0">
          {index + 1}
        </span>

        <span className="text-[#00d4ff]">{icon}</span>

        <span className="px-2 py-0.5 border rounded text-[10px] uppercase font-mono bg-[#00d4ff]/10 text-[#00d4ff] border-[#00d4ff]/30">
          {step.type}
        </span>

        <span className="font-mono text-sm text-gray-300 truncate flex-1">
          {step.name || 'Untitled Step'}
        </span>

        <span
          className={`px-2 py-0.5 border rounded text-[10px] uppercase font-mono ${modeColor}`}
        >
          {step.mode}
        </span>

        {expanded ? (
          <ChevronUp className="h-4 w-4 text-gray-500 shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500 shrink-0" />
        )}
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-[#1a1a1a] p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Step Name
            </label>
            <input
              type="text"
              value={step.name}
              onChange={(e) => onChange({ ...step, name: e.target.value })}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#D4A039]"
            />
          </div>

          {/* Type */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Step Type
            </label>
            <select
              value={step.type}
              onChange={(e) => onChange({ ...step, type: e.target.value })}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#D4A039]"
            >
              <option value="search">Search</option>
              <option value="extract">Extract</option>
              <option value="analyze">Analyze</option>
              <option value="synthesize">Synthesize</option>
              <option value="filter">Filter</option>
            </select>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Description
            </label>
            <textarea
              value={step.description || ''}
              onChange={(e) =>
                onChange({ ...step, description: e.target.value || undefined })
              }
              rows={2}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#D4A039] resize-none"
              placeholder="What this step does..."
            />
          </div>

          {/* Parameters JSON */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Parameters (JSON)
            </label>
            <textarea
              value={paramsText}
              onChange={(e) => handleParamsChange(e.target.value)}
              rows={4}
              className={`w-full px-3 py-2 bg-[#1a1a1a] border rounded text-sm font-mono text-gray-300 focus:outline-none resize-none ${
                paramsError
                  ? 'border-red-500/50 focus:border-red-500'
                  : 'border-[#333] focus:border-[#D4A039]'
              }`}
            />
            {paramsError && (
              <p className="mt-1 text-xs text-red-400 font-mono">
                {paramsError}
              </p>
            )}
          </div>

          {/* Model selector */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Model
            </label>
            <select
              value={step.model_id || ''}
              onChange={(e) =>
                onChange({ ...step, model_id: e.target.value || undefined })
              }
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#D4A039]"
            >
              <option value="">Default</option>
              {MODEL_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Mode toggle */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Mode
            </label>
            <button
              onClick={handleModeToggle}
              className={`px-3 py-1.5 border rounded text-xs uppercase font-mono transition-colors ${modeColor}`}
            >
              {step.mode}
            </button>
          </div>

          {/* Temperature slider */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Temperature{' '}
              {step.mode === 'deterministic' && (
                <span className="text-gray-600">(disabled)</span>
              )}
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={step.temperature ?? 0.7}
                onChange={(e) =>
                  onChange({ ...step, temperature: parseFloat(e.target.value) })
                }
                disabled={step.mode === 'deterministic'}
                className="flex-1 accent-[#ffb700] disabled:opacity-30"
              />
              <span className="text-xs font-mono text-gray-400 w-8 text-right">
                {(step.temperature ?? 0.7).toFixed(1)}
              </span>
            </div>
          </div>

          {/* Seed input */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Seed
            </label>
            <input
              type="number"
              value={step.seed ?? ''}
              onChange={(e) =>
                onChange({
                  ...step,
                  seed: e.target.value
                    ? parseInt(e.target.value, 10)
                    : undefined,
                })
              }
              placeholder="Optional seed for reproducibility"
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#D4A039]"
            />
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-2 border-t border-[#1a1a1a]">
            <button
              onClick={onMoveUp}
              disabled={index === 0}
              className="p-1.5 text-gray-500 hover:text-[#D4A039] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Move step up"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
            <button
              onClick={onMoveDown}
              disabled={index === totalSteps - 1}
              className="p-1.5 text-gray-500 hover:text-[#D4A039] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Move step down"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
            <div className="flex-1" />
            <button
              onClick={onRemove}
              className="p-1.5 text-gray-500 hover:text-red-400 transition-colors"
              aria-label="Remove step"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default StepCard;
