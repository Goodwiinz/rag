'use client';

/**
 * Research Projects List Page
 * Displays all projects with search, create, and management options
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Search, FolderOpen, FileText, BookOpen, Loader2, Trash2 } from 'lucide-react';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/stores/authStore';
import { workspaceService } from '@/services/workspaceService';
import type { Project, ProjectCreate } from '@/services/projectService';

export default function ProjectsPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const {
    projects,
    loading,
    error,
    total,
    fetchProjects,
    createProject,
    deleteProject,
    clearError,
  } = useProjectStore();

  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchProjects({ search: searchQuery || undefined });
    }
  }, [mounted, isAuthenticated, searchQuery, fetchProjects]);

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;

    setCreating(true);
    try {
      // Get or create default workspace for the project
      const workspace = await workspaceService.getOrCreateDefaultWorkspace();

      const project = await createProject({
        workspace_id: workspace.id,
        name: newProjectName.trim(),
        description: newProjectDescription.trim() || undefined,
      });
      setShowCreateModal(false);
      setNewProjectName('');
      setNewProjectDescription('');
      router.push(`/projects/${project.id}`);
    } catch (err) {
      console.error('Failed to create project:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      await deleteProject(projectId);
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  };

  if (!mounted) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-[#00ff9f]" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-mono font-bold text-[#00ff9f]">Research Projects</h1>
          <p className="text-sm text-gray-500 mt-1">
            Organize documents, citations, and notes into research projects
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded-lg font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 bg-[#1a1a1a] border border-[#333] rounded-lg text-sm font-mono text-gray-300 placeholder-gray-500 focus:outline-none focus:border-[#00ff9f]"
          />
        </div>
      </div>

      {/* Error Display */}
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

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-[#00ff9f]" />
        </div>
      )}

      {/* Empty State */}
      {!loading && projects.length === 0 && (
        <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
          <FolderOpen className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-mono text-gray-400 mb-2">No projects yet</h3>
          <p className="text-sm text-gray-500 mb-4">
            Create your first research project to get started
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded-lg font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Create Project
          </button>
        </div>
      )}

      {/* Projects Grid */}
      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <div
              key={project.id}
              onClick={() => router.push(`/projects/${project.id}`)}
              className="group bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4 cursor-pointer hover:border-[#00ff9f]/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FolderOpen className="h-5 w-5 text-[#00ff9f]" />
                  <h3 className="font-mono font-medium text-gray-200 group-hover:text-[#00ff9f] transition-colors">
                    {project.name}
                  </h3>
                </div>
                <button
                  onClick={(e) => handleDeleteProject(project.id, e)}
                  className="p-1 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Delete project"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              {project.description && (
                <p className="text-sm text-gray-500 mb-3 line-clamp-2">
                  {project.description}
                </p>
              )}

              <div className="flex items-center gap-4 text-xs text-gray-500 font-mono">
                <div className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  <span>{project.document_count || 0} docs</span>
                </div>
                <div className="flex items-center gap-1">
                  <BookOpen className="h-3 w-3" />
                  <span>{project.citation_count || 0} citations</span>
                </div>
              </div>

              <div className="mt-3 text-xs text-gray-600 font-mono">
                Updated {new Date(project.updated_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats */}
      {!loading && total > 0 && (
        <div className="mt-6 text-center text-sm text-gray-500 font-mono">
          Showing {projects.length} of {total} projects
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-md p-6">
            <h2 className="text-lg font-mono font-bold text-[#00ff9f] mb-4">
              Create New Project
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                  Project Name *
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="e.g., ML Research 2024"
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                  Description (optional)
                </label>
                <textarea
                  value={newProjectDescription}
                  onChange={(e) => setNewProjectDescription(e.target.value)}
                  placeholder="Brief description of your research project..."
                  rows={3}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f] resize-none"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewProjectName('');
                  setNewProjectDescription('');
                }}
                className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim() || creating}
                className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
