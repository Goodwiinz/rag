'use client';

import { LayoutGrid, List } from 'lucide-react';
import type { Project } from '@/services/projectService';
import { ProjectCard } from './ProjectCard';

export interface ProjectListProps {
  projects: Project[];
  viewMode: 'grid' | 'list';
  onViewModeChange: (viewMode: 'grid' | 'list') => void;
  onOpenProject: (projectId: string) => void;
  onDeleteProject?: (projectId: string) => void;
  onArchiveProject?: (projectId: string) => void;
}

export function ProjectList({
  projects,
  viewMode,
  onViewModeChange,
  onOpenProject,
  onDeleteProject,
  onArchiveProject,
}: ProjectListProps) {
  return (
    <div>
      <div className="flex justify-end mb-4">
        <div className="inline-flex items-center border border-[#333] rounded-lg overflow-hidden">
          <button
            onClick={() => onViewModeChange('grid')}
            className={`px-3 py-2 text-xs font-mono flex items-center gap-1.5 ${
              viewMode === 'grid'
                ? 'bg-[#00ff9f]/10 text-[#00ff9f]'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-gray-300'
            }`}
            title="Grid view"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            Grid
          </button>
          <button
            onClick={() => onViewModeChange('list')}
            className={`px-3 py-2 text-xs font-mono flex items-center gap-1.5 ${
              viewMode === 'list'
                ? 'bg-[#00ff9f]/10 text-[#00ff9f]'
                : 'bg-[#1a1a1a] text-gray-400 hover:text-gray-300'
            }`}
            title="List view"
          >
            <List className="h-3.5 w-3.5" />
            List
          </button>
        </div>
      </div>

      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={onOpenProject}
              onDelete={onDeleteProject}
              onArchive={onArchiveProject}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={onOpenProject}
              onDelete={onDeleteProject}
              onArchive={onArchiveProject}
              compact
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default ProjectList;
