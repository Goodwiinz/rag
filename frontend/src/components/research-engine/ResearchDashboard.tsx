'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Loader2, Plus, Sparkles } from 'lucide-react';
import { listProjects, listTemplates } from '@/services/researchEngineService';
import {
  useResearchEngineStore,
  type ResearchProject,
} from '@/store/research-engine-store';
import { ProjectCard } from './ProjectCard';
import { CreateProjectModal } from './CreateProjectModal';

interface Template {
  id: string;
  name: string;
  description?: string;
}

export function ResearchDashboard() {
  const { projects, setProjects, isLoading, setLoading, error, setError } =
    useResearchEngineStore();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = (await listProjects()) as { data?: ResearchProject[] };
      setProjects(res.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [setProjects, setLoading, setError]);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = (await listTemplates()) as { data?: Template[] };
      setTemplates(res.data ?? []);
    } catch {
      // Templates are non-critical; silently ignore
    }
  }, []);

  useEffect(() => {
    fetchProjects();
    fetchTemplates();
  }, [fetchProjects, fetchTemplates]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-mono font-bold text-[#00ff9f]">
            Research Engine
          </h1>
          <p className="text-sm text-gray-500 font-mono mt-1">
            Create and manage reproducible research workflows with
            blueprint-driven pipelines.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {/* Quick-start templates */}
      {templates.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wide mb-3">
            Quick-start Templates
          </h2>
          <div className="flex flex-wrap gap-2">
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                title={tpl.description}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#00d4ff]/5 text-[#00d4ff] border border-[#00d4ff]/20 rounded font-mono text-xs hover:bg-[#00d4ff]/10 transition-colors"
              >
                <Sparkles className="h-3 w-3" />
                {tpl.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-[#00ff9f]" />
          <span className="ml-2 font-mono text-sm text-gray-500">
            Loading projects...
          </span>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded mb-6">
          <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
          <span className="text-sm text-red-400 font-mono">{error}</span>
        </div>
      )}

      {/* Project list */}
      {!isLoading && !error && (
        <>
          {projects.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-gray-500 font-mono text-sm">
                No projects yet. Create one to get started.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Create modal */}
      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={fetchProjects}
      />
    </div>
  );
}

export default ResearchDashboard;
