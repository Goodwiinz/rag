'use client';

import { useCallback, useEffect, useState } from 'react';
import { FileText, Loader2, Sparkles } from 'lucide-react';
import { listTemplates } from '@/services/researchEngineService';
import type { BlueprintStepDef } from '@/services/researchEngineService';

interface Template {
  slug: string;
  name: string;
  description?: string;
  step_count: number;
  steps?: BlueprintStepDef[];
  parameters?: Record<string, unknown>;
}

export interface TemplateSelectorProps {
  onSelect: (template: Template | null) => void;
}

export function TemplateSelector({ onSelect }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = (await listTemplates()) as Template[];
      setTemplates(res ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
        <span className="ml-2 font-mono text-sm text-gray-500">
          Loading templates...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-400 font-mono">
        {error}
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-mono font-bold text-[#00ff9f] mb-2">
        Choose a Blueprint Template
      </h2>
      <p className="text-sm text-gray-500 font-mono mb-6">
        Select a template to get started or create a blank blueprint.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Blank blueprint option */}
        <button
          onClick={() => onSelect(null)}
          className="group bg-[#0a0a0a] border border-dashed border-[#333] rounded-lg p-5 text-left hover:border-[#00ff9f]/50 transition-colors"
        >
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-5 w-5 text-gray-500 group-hover:text-[#00ff9f] transition-colors" />
            <span className="font-mono font-medium text-gray-300 group-hover:text-[#00ff9f] transition-colors">
              Blank Blueprint
            </span>
          </div>
          <p className="text-sm text-gray-600 font-mono">
            Start from scratch with an empty blueprint.
          </p>
          <div className="mt-3 text-xs text-gray-600 font-mono">0 steps</div>
        </button>

        {/* Template cards */}
        {templates.map((tpl) => (
          <button
            key={tpl.slug}
            onClick={() => onSelect(tpl)}
            className="group bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-5 text-left hover:border-[#00d4ff]/50 transition-colors"
          >
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="h-5 w-5 text-[#00d4ff] shrink-0" />
              <span className="font-mono font-medium text-gray-300 group-hover:text-[#00d4ff] transition-colors truncate">
                {tpl.name}
              </span>
            </div>
            {tpl.description && (
              <p className="text-sm text-gray-500 font-mono mb-3 line-clamp-2">
                {tpl.description}
              </p>
            )}
            <div className="text-xs text-gray-600 font-mono">
              {tpl.step_count} step{tpl.step_count !== 1 ? 's' : ''}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default TemplateSelector;
