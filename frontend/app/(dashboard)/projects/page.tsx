'use client';

/**
 * Research Projects List Page
 * Displays all projects with search, filters, and management options.
 */

import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import { FolderOpen, Loader2, Network, Plus, Search } from 'lucide-react';
import { CreateProjectModal } from '@/components/research/CreateProjectModal';
import { ProjectList } from '@/components/research/ProjectList';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/stores/authStore';
import { useChatStore, selectCurrentWorkspace } from '@/store/chat-store';
import { workspaceService } from '@/services/workspaceService';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';

type ProjectStatus = 'active' | 'paused' | 'completed' | 'archived';
type ProjectType = 'research' | 'literature_review' | 'thesis' | 'paper';

export default function ProjectsPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const currentWorkspace = useChatStore(selectCurrentWorkspace);
  const {
    projects,
    loading,
    error,
    total,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
    clearError,
  } = useProjectStore();

  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<ProjectType | ''>('');
  const [tagFilter, setTagFilter] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !isAuthenticated) return;
    // Cancel the previous fetch when filters/workspace change so a slow response
    // from the earlier request can't overwrite the latest results.
    const controller = new AbortController();
    void fetchProjects(
      {
        workspace_id: currentWorkspace?.id || undefined,
        search: searchQuery || undefined,
        project_status: statusFilter || undefined,
        project_type: typeFilter || undefined,
        tag: tagFilter || undefined,
      },
      { signal: controller.signal }
    );
    return () => controller.abort();
  }, [
    mounted,
    isAuthenticated,
    currentWorkspace?.id,
    searchQuery,
    statusFilter,
    typeFilter,
    tagFilter,
    fetchProjects,
  ]);

  const allTags = useMemo(() => {
    return Array.from(
      new Set(projects.flatMap((project) => project.tags || []))
    ).sort();
  }, [projects]);

  const handleCreateProject = async (payload: {
    name: string;
    description?: string;
    project_type?: ProjectType;
    deadline?: string;
    tags?: string[];
  }) => {
    // Let the modal surface the toast on failure (it keeps the form open for
    // retry). Rethrow so the modal's catch block fires instead of silently
    // resolving.
    const workspace = await workspaceService.getOrCreateDefaultWorkspace();
    const project = await createProject({
      workspace_id: workspace.id,
      name: payload.name,
      description: payload.description,
      project_type: payload.project_type,
      deadline: payload.deadline,
      tags: payload.tags,
    });
    router.push(`/projects/${project.id}`);
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('Are you sure you want to delete this project?')) return;
    // Clear any leftover error from a previous action so the banner doesn't
    // linger under a successful toast.
    clearError();
    try {
      await deleteProject(projectId);
      toast.success('Project deleted');
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to delete project'));
    }
  };

  const handleArchiveProject = async (projectId: string) => {
    clearError();
    try {
      await updateProject(projectId, { research_status: 'archived' });
      toast.success('Project archived');
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to archive project'));
    }
  };

  if (!mounted) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-mono font-bold text-primary">
            RESEARCH_PROJECTS
          </h1>
          {currentWorkspace && (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-wider mt-1">
              <Network className="w-3 h-3 text-[var(--phosphor-green)]" />
              {currentWorkspace.name}
            </span>
          )}
          <p className="text-sm font-mono text-muted-foreground mt-1">
            Organize documents, citations, and notes into research projects
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-lg font-mono text-sm hover:bg-primary/20 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create Project
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg text-sm font-mono text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value as ProjectStatus | '')
          }
          className="px-3 py-2 bg-muted border border-border rounded text-sm font-mono text-foreground focus:outline-none focus:border-primary"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as ProjectType | '')}
          className="px-3 py-2 bg-muted border border-border rounded text-sm font-mono text-foreground focus:outline-none focus:border-primary"
        >
          <option value="">All types</option>
          <option value="research">Research</option>
          <option value="literature_review">Literature Review</option>
          <option value="thesis">Thesis</option>
          <option value="paper">Paper</option>
        </select>
      </div>

      {allTags.length > 0 && (
        <div className="mb-6 flex items-center flex-wrap gap-2">
          <span className="text-xs text-muted-foreground font-mono">Tags:</span>
          <button
            onClick={() => setTagFilter('')}
            className={`px-2 py-1 border rounded text-xs font-mono ${
              tagFilter === ''
                ? 'bg-primary/10 border-primary/30 text-primary'
                : 'bg-muted border-border text-muted-foreground'
            }`}
          >
            All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setTagFilter(tag)}
              className={`px-2 py-1 border rounded text-xs font-mono ${
                tagFilter === tag
                  ? 'bg-primary/10 border-primary/30 text-primary'
                  : 'bg-muted border-border text-muted-foreground'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 font-mono text-sm">{error}</p>
          <button
            onClick={clearError}
            className="mt-2 text-xs text-red-400 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {!loading && projects.length === 0 && (
        <div className="text-center py-12 bg-card border border-border rounded-lg">
          <FolderOpen className="h-12 w-12 text-muted-foreground/40 mx-auto mb-4" />
          <h3 className="text-lg font-mono text-foreground mb-2">
            NO_ACTIVE_RESEARCH
          </h3>
          <p className="text-sm font-mono text-muted-foreground mb-4">
            Initialize your first research project to begin building your
            knowledge graph.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-lg font-mono text-sm hover:bg-primary/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Create Project
          </button>
        </div>
      )}

      {!loading && projects.length > 0 && (
        <ProjectList
          projects={projects}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onOpenProject={(projectId) => router.push(`/projects/${projectId}`)}
          onDeleteProject={(projectId) => {
            void handleDeleteProject(projectId);
          }}
          onArchiveProject={(projectId) => {
            void handleArchiveProject(projectId);
          }}
        />
      )}

      {!loading && total > 0 && (
        <div className="mt-6 text-center text-sm text-muted-foreground font-mono">
          Showing {projects.length} of {total} projects
        </div>
      )}

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateProject}
      />
    </div>
  );
}
