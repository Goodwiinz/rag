'use client';

import {
  Calendar,
  FileText,
  FolderKanban,
  MoreHorizontal,
  Trash2,
} from 'lucide-react';
import type { Project } from '@/services/projectService';

export interface ProjectCardProps {
  project: Project;
  onOpen: (projectId: string) => void;
  onDelete?: (projectId: string) => void;
  onArchive?: (projectId: string) => void;
  compact?: boolean;
}

const statusStyles: Record<string, string> = {
  active: 'bg-primary/10 text-primary border-primary/30',
  paused:
    'bg-[var(--amber-gold)]/10 text-[var(--amber-gold)] border-[var(--amber-gold)]/30',
  completed: 'bg-[var(--cyan)]/10 text-[var(--cyan)] border-[var(--cyan)]/30',
  archived: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
};

export function ProjectCard({
  project,
  onOpen,
  onDelete,
  onArchive,
  compact = false,
}: ProjectCardProps) {
  const status = project.research_status || 'active';
  const statusClass = statusStyles[status] || statusStyles.active;
  const createdLabel = project.updated_at
    ? new Date(project.updated_at).toLocaleDateString()
    : '';

  return (
    <div
      onClick={() => onOpen(project.id)}
      className="group bg-card border border-border rounded-lg p-4 cursor-pointer hover:border-primary/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5 text-primary shrink-0" />
            <h3 className="font-mono font-medium text-foreground truncate group-hover:text-primary transition-colors">
              {project.name}
            </h3>
          </div>
          <div className="mt-2">
            <span
              className={`px-2 py-0.5 border rounded text-[11px] uppercase font-mono ${statusClass}`}
            >
              {status}
            </span>
          </div>
        </div>

        {(onDelete || onArchive) && (
          <div
            className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"
            onClick={(e) => e.stopPropagation()}
          >
            {onArchive && (
              <button
                onClick={() => onArchive(project.id)}
                className="p-1 text-muted-foreground hover:text-[var(--amber-gold)] transition-colors"
                title="Archive project"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            )}
            {onDelete && (
              <button
                onClick={() => onDelete(project.id)}
                className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                title="Delete project"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>

      {project.description && (
        <p
          className={`text-sm text-gray-500 mb-3 ${compact ? 'line-clamp-1' : 'line-clamp-2'}`}
        >
          {project.description}
        </p>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-500 font-mono">
        <div className="flex items-center gap-1">
          <FileText className="h-3 w-3" />
          <span>{project.document_count || 0} docs</span>
        </div>
        {project.deadline && (
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{new Date(project.deadline).toLocaleDateString()}</span>
          </div>
        )}
      </div>

      {project.tags && project.tags.length > 0 && (
        <div className="flex items-center flex-wrap gap-1 mt-3">
          {project.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[11px] font-mono"
            >
              {tag}
            </span>
          ))}
          {project.tags.length > 3 && (
            <span className="text-[11px] text-gray-500 font-mono">
              +{project.tags.length - 3}
            </span>
          )}
        </div>
      )}

      <div className="mt-3 text-xs text-gray-600 font-mono">
        Updated {createdLabel}
      </div>
    </div>
  );
}

export default ProjectCard;
