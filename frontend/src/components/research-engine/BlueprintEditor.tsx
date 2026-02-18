'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Play,
  Plus,
  Save,
} from 'lucide-react';
import {
  getProject,
  getBlueprint,
  createBlueprint,
  startRun,
} from '@/services/researchEngineService';
import type { BlueprintStepDef } from '@/services/researchEngineService';
import type { ResearchProject } from '@/store/research-engine-store';
import { StepCard } from './StepCard';
import { TemplateSelector } from './TemplateSelector';

interface Blueprint {
  id: string;
  name: string;
  steps: BlueprintStepDef[];
  parameters: Record<string, unknown>;
  template_source?: string;
}

interface TemplateData {
  id: string;
  name: string;
  description?: string;
  steps: BlueprintStepDef[];
  parameters?: Record<string, unknown>;
}

let _stepKeyCounter = 0;
function nextStepKey(): string {
  return `step_${Date.now()}_${_stepKeyCounter++}`;
}

type StepWithKey = BlueprintStepDef & { _key: string };

function withKey(step: BlueprintStepDef): StepWithKey {
  return { ...step, _key: nextStepKey() };
}

const DEFAULT_STEP: BlueprintStepDef = {
  type: 'search',
  name: '',
  description: '',
  parameters: {},
  mode: 'deterministic',
};

export interface BlueprintEditorProps {
  projectId: string;
}

export function BlueprintEditor({ projectId }: BlueprintEditorProps) {
  const router = useRouter();

  const [project, setProject] = useState<ResearchProject | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);

  // Editor state
  const [blueprintName, setBlueprintName] = useState('');
  const [steps, setSteps] = useState<StepWithKey[]>([]);
  const [globalParams, setGlobalParams] = useState<Record<string, unknown>>({});
  const [globalParamsText, setGlobalParamsText] = useState('{}');
  const [globalParamsError, setGlobalParamsError] = useState<string | null>(
    null
  );

  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const projectRes = (await getProject(projectId)) as {
        data?: ResearchProject & { blueprint_id?: string };
      };
      const proj = projectRes.data;
      if (!proj) {
        setError('Project not found');
        return;
      }
      setProject(proj);

      // Try to load existing blueprint
      if (proj.blueprint_id) {
        try {
          const bpRes = (await getBlueprint(proj.blueprint_id)) as {
            data?: Blueprint;
          };
          if (bpRes.data) {
            setBlueprint(bpRes.data);
            setBlueprintName(bpRes.data.name);
            setSteps(bpRes.data.steps.map(withKey));
            setGlobalParams(bpRes.data.parameters);
            setGlobalParamsText(JSON.stringify(bpRes.data.parameters, null, 2));
            return;
          }
        } catch {
          // Blueprint may not exist yet, show template selector
        }
      }

      // No blueprint found, show template selector
      setShowTemplateSelector(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTemplateSelect = (template: TemplateData | null) => {
    setShowTemplateSelector(false);
    if (template) {
      setBlueprintName(template.name);
      setSteps(template.steps.map(withKey));
      const params = template.parameters ?? {};
      setGlobalParams(params);
      setGlobalParamsText(JSON.stringify(params, null, 2));
    } else {
      // Blank blueprint
      setBlueprintName(
        project?.name ? `${project.name} Blueprint` : 'New Blueprint'
      );
      setSteps([]);
      setGlobalParams({});
      setGlobalParamsText('{}');
    }
  };

  const handleGlobalParamsChange = (value: string) => {
    setGlobalParamsText(value);
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      setGlobalParamsError(null);
      setGlobalParams(parsed);
    } catch {
      setGlobalParamsError('Invalid JSON');
    }
  };

  const handleStepChange = (index: number, updated: BlueprintStepDef) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...updated, _key: s._key } : s))
    );
  };

  const handleMoveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    setSteps((prev) => {
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const handleRemoveStep = (index: number) => {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddStep = () => {
    setSteps((prev) => [...prev, withKey({ ...DEFAULT_STEP })]);
  };

  const handleSave = async () => {
    if (!blueprintName.trim()) return;
    if (globalParamsError) return;

    setSaving(true);
    setError(null);
    try {
      const cleanSteps = steps.map(({ _key, ...rest }) => rest);
      const res = (await createBlueprint(projectId, {
        name: blueprintName.trim(),
        steps: cleanSteps,
        parameters: globalParams,
      })) as { data?: Blueprint };

      if (res.data) {
        setBlueprint(res.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save blueprint');
    } finally {
      setSaving(false);
    }
  };

  const handleStartRun = async () => {
    if (!blueprint?.id) return;

    setStarting(true);
    setError(null);
    try {
      const res = (await startRun(blueprint.id, globalParams)) as {
        data?: { id: string };
      };
      if (res.data?.id) {
        router.push(`/research-engine/runs/${res.data.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
      setStarting(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
        <span className="ml-2 font-mono text-sm text-gray-500">
          Loading project...
        </span>
      </div>
    );
  }

  // Template selector
  if (showTemplateSelector) {
    return (
      <div>
        <button
          onClick={() => router.push('/research-engine')}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-[#00ff9f] font-mono mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </button>
        {project && (
          <h1 className="text-xl font-mono font-bold text-gray-200 mb-6">
            {project.name}
          </h1>
        )}
        <TemplateSelector onSelect={handleTemplateSelect} />
      </div>
    );
  }

  // Editor
  return (
    <div>
      {/* Navigation */}
      <button
        onClick={() => router.push('/research-engine')}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-[#00ff9f] font-mono mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Projects
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1 min-w-0">
          <input
            type="text"
            value={blueprintName}
            onChange={(e) => setBlueprintName(e.target.value)}
            className="text-xl font-mono font-bold bg-transparent text-gray-200 border-none outline-none w-full focus:text-[#00ff9f] transition-colors placeholder-gray-600"
            placeholder="Blueprint name..."
          />
          {project && (
            <p className="text-sm text-gray-500 font-mono mt-1">
              Project: {project.name}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleSave}
            disabled={saving || !blueprintName.trim() || !!globalParamsError}
            className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </button>

          {blueprint && (
            <button
              onClick={handleStartRun}
              disabled={starting || steps.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/30 rounded font-mono text-sm hover:bg-[#ffb700]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {starting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Start Run
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded mb-6">
          <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
          <span className="text-sm text-red-400 font-mono">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Steps list */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wide">
              Steps ({steps.length})
            </h2>
            <button
              onClick={handleAddStep}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-mono text-[#00ff9f] border border-[#00ff9f]/30 rounded hover:bg-[#00ff9f]/10 transition-colors"
            >
              <Plus className="h-3 w-3" />
              Add Step
            </button>
          </div>

          {steps.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-[#333] rounded-lg">
              <p className="text-gray-600 font-mono text-sm mb-3">
                No steps yet.
              </p>
              <button
                onClick={handleAddStep}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-mono text-[#00ff9f] border border-[#00ff9f]/30 rounded hover:bg-[#00ff9f]/10 transition-colors"
              >
                <Plus className="h-3 w-3" />
                Add your first step
              </button>
            </div>
          ) : (
            steps.map((step, idx) => (
              <StepCard
                key={step._key}
                step={step}
                index={idx}
                totalSteps={steps.length}
                onChange={(updated) => handleStepChange(idx, updated)}
                onMoveUp={() => handleMoveStep(idx, -1)}
                onMoveDown={() => handleMoveStep(idx, 1)}
                onRemove={() => handleRemoveStep(idx)}
              />
            ))
          )}
        </div>

        {/* Global parameters sidebar */}
        <div className="space-y-4">
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
            <h3 className="text-sm font-mono text-gray-400 uppercase tracking-wide mb-3">
              Global Parameters
            </h3>

            {/* Quick fields for common params */}
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-xs text-gray-500 font-mono mb-1">
                  Topic
                </label>
                <input
                  type="text"
                  value={(globalParams.topic as string) ?? ''}
                  onChange={(e) =>
                    setGlobalParams((prev) => {
                      const next = {
                        ...prev,
                        topic: e.target.value || undefined,
                      };
                      if (!next.topic) delete next.topic;
                      setGlobalParamsText(JSON.stringify(next, null, 2));
                      return next;
                    })
                  }
                  placeholder="Research topic..."
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-500 font-mono mb-1">
                  Date Range Start
                </label>
                <input
                  type="date"
                  value={(globalParams.date_start as string) ?? ''}
                  onChange={(e) =>
                    setGlobalParams((prev) => {
                      const next = {
                        ...prev,
                        date_start: e.target.value || undefined,
                      };
                      if (!next.date_start) delete next.date_start;
                      setGlobalParamsText(JSON.stringify(next, null, 2));
                      return next;
                    })
                  }
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-500 font-mono mb-1">
                  Date Range End
                </label>
                <input
                  type="date"
                  value={(globalParams.date_end as string) ?? ''}
                  onChange={(e) =>
                    setGlobalParams((prev) => {
                      const next = {
                        ...prev,
                        date_end: e.target.value || undefined,
                      };
                      if (!next.date_end) delete next.date_end;
                      setGlobalParamsText(JSON.stringify(next, null, 2));
                      return next;
                    })
                  }
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
                />
              </div>
            </div>

            {/* Raw JSON editor */}
            <div>
              <label className="block text-xs text-gray-500 font-mono mb-1">
                Raw JSON
              </label>
              <textarea
                value={globalParamsText}
                onChange={(e) => handleGlobalParamsChange(e.target.value)}
                rows={6}
                className={`w-full px-3 py-2 bg-[#1a1a1a] border rounded text-xs font-mono text-gray-300 focus:outline-none resize-none ${
                  globalParamsError
                    ? 'border-red-500/50 focus:border-red-500'
                    : 'border-[#333] focus:border-[#00ff9f]'
                }`}
              />
              {globalParamsError && (
                <p className="mt-1 text-xs text-red-400 font-mono">
                  {globalParamsError}
                </p>
              )}
            </div>
          </div>

          {/* Blueprint info */}
          {blueprint && (
            <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
              <h3 className="text-sm font-mono text-gray-400 uppercase tracking-wide mb-2">
                Blueprint Info
              </h3>
              <div className="space-y-1 text-xs font-mono text-gray-500">
                <p>
                  ID: <span className="text-gray-400">{blueprint.id}</span>
                </p>
                {blueprint.template_source && (
                  <p>
                    Template:{' '}
                    <span className="text-[#00d4ff]">
                      {blueprint.template_source}
                    </span>
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default BlueprintEditor;
