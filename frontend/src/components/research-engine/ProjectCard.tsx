'use client';

import { Calendar, FolderKanban } from 'lucide-react';
import { useRouter } from 'next/navigation';
import type { ResearchProject } from '@/store/research-engine-store';

const statusStyles: Record<string, string> = {
  active: 'bg-[#D4A039]/10 text-[#D4A039] border-[#D4A039]/30',
  paused: 'bg-[#ffb700]/10 text-[#ffb700] border-[#ffb700]/30',
  completed: 'bg-[#00d4ff]/10 text-[#00d4ff] border-[#00d4ff]/30',
  archived: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
};

export interface ProjectCardProps {
  project: ResearchProject;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const router = useRouter();
  const status = project.status || 'active';
  const statusClass = statusStyles[status] || statusStyles.active;

  const createdDate = project.created_at
    ? new Date(project.created_at).toLocaleDateString()
    : '';

  return (
    <div
      onClick={() =>
        router.push(`/research-engine/projects/${project.id}/blueprint`)
      }
      className="group bg-card border border-border rounded-lg p-4 cursor-pointer hover:border-primary/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <FolderKanban className="h-5 w-5 text-[#D4A039] shrink-0" />
            <h3 className="font-mono font-medium text-gray-200 truncate group-hover:text-[#D4A039] transition-colors">
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
      </div>

      {project.description && (
        <p className="text-sm text-gray-500 mb-3 line-clamp-2">
          {project.description}
        </p>
      )}

      {createdDate && (
        <div className="flex items-center gap-1 text-xs text-gray-600 font-mono">
          <Calendar className="h-3 w-3" />
          <span>Created {createdDate}</span>
        </div>
      )}
    </div>
  );
}

export default ProjectCard;
