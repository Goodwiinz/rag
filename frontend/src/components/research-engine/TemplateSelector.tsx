'use client';

import { useCallback, useEffect, useState } from 'react';
import { FileText, Sparkles } from 'lucide-react';
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
      <div>
        <div className="h-6 w-64 rounded bg-muted animate-pulse mb-2" />
        <div className="h-4 w-80 rounded bg-muted animate-pulse mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-32 rounded-xl border border-border bg-card animate-pulse"
            />
          ))}
        </div>
        <span className="sr-only" role="status">
          Loading templates
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 p-4 rounded-xl border border-destructive/30 bg-destructive/5"
      >
        <div className="flex-1">
          <p className="text-sm text-foreground">{error}</p>
          <button
            type="button"
            onClick={fetchTemplates}
            className="mt-1 text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-foreground mb-2">
        Choose a blueprint template
      </h2>
      <p className="text-sm text-muted-foreground mb-6">
        Select a template to get started, or create a blank blueprint.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Blank blueprint option */}
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="group rounded-xl border border-dashed border-border bg-card p-5 text-left hover:border-primary/40 hover:bg-muted/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <div className="flex items-center gap-2 mb-3">
            <FileText
              aria-hidden="true"
              className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors"
            />
            <span className="font-medium text-foreground">Blank blueprint</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Start from scratch with an empty blueprint.
          </p>
          <div className="mt-3 text-xs text-muted-foreground tabular-nums">
            0 steps
          </div>
        </button>

        {/* Template cards */}
        {templates.map((tpl) => (
          <button
            type="button"
            key={tpl.slug}
            onClick={() => onSelect(tpl)}
            className="group rounded-xl border border-border bg-card p-5 text-left hover:border-primary/40 hover:shadow-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="flex items-center gap-2 mb-3">
              <Sparkles
                aria-hidden="true"
                className="h-5 w-5 text-primary shrink-0"
              />
              <span className="font-medium text-foreground truncate">
                {tpl.name}
              </span>
            </div>
            {tpl.description && (
              <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                {tpl.description}
              </p>
            )}
            <div className="text-xs text-muted-foreground tabular-nums">
              {tpl.step_count} step{tpl.step_count !== 1 ? 's' : ''}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default TemplateSelector;
