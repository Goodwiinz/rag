'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, FolderOpen, Loader2, Plus, Sparkles } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
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
      const res = (await listProjects()) as ResearchProject[];
      setProjects(res ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [setProjects, setLoading, setError]);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = (await listTemplates()) as Template[];
      setTemplates(res ?? []);
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
          <h1 className="text-2xl font-mono font-bold text-[var(--terminal-text)] tracking-wider">
            RESEARCH_ENGINE
          </h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5 uppercase tracking-widest">
            Create and manage reproducible research workflows with
            blueprint-driven pipelines.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded font-mono text-sm hover:bg-primary/20 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {/* Quick-start templates */}
      {templates.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-mono text-muted-foreground uppercase tracking-wide mb-3">
            Quick-start Templates
          </h2>
          <div className="flex flex-wrap gap-2">
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                title={tpl.description}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--cyan)]/5 text-[var(--cyan)] border border-[var(--cyan)]/20 rounded font-mono text-xs hover:bg-[var(--cyan)]/10 transition-colors"
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
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="ml-2 font-mono text-sm text-muted-foreground">
            Loading projects...
          </span>
        </div>
      )}

      {/* Error state — graceful fallback instead of alarming red banner */}
      {error && !isLoading && (
        <EmptyState
          icon={AlertCircle}
          title="SERVICE_UNAVAILABLE"
          description="The Research Engine service is not responding. This may be a temporary issue."
          action={{
            label: 'RETRY_CONNECTION',
            onClick: () => window.location.reload(),
          }}
        />
      )}

      {/* Project list */}
      {!isLoading && !error && (
        <>
          {projects.length === 0 ? (
            <EmptyState
              icon={FolderOpen}
              title="NO_PROJECTS_FOUND"
              description="Create your first research project to start organizing documents and workflows."
            />
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
