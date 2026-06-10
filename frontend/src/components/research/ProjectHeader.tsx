'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft, Calendar, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Project } from '@/services/projectService';

interface ProjectHeaderProps {
  project: Project;
}

const statusVariant: Record<
  string,
  'success' | 'warning' | 'info' | 'secondary'
> = {
  active: 'success',
  paused: 'warning',
  completed: 'info',
  archived: 'secondary',
};

const typeLabels: Record<string, string> = {
  research: 'Research',
  literature_review: 'Literature Review',
  thesis: 'Thesis',
  paper: 'Paper',
};

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
  if (diffDays === 0) return 'Due today';
  if (diffDays <= 7) return `Due in ${diffDays}d`;
  if (diffDays <= 30) return `Due in ${Math.round(diffDays / 7)}w`;
  return `Due ${date.toLocaleDateString()}`;
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  const router = useRouter();

  return (
    <div className="mb-4 sm:mb-8 space-y-2 sm:space-y-4">
      {/* Back link */}
      <button
        onClick={() => router.push('/projects')}
        className="inline-flex items-center gap-1.5 text-xs sm:text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
        Projects
      </button>

      {/* Hero card */}
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="space-y-2 sm:space-y-3">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <h1 className="text-lg sm:text-2xl font-semibold tracking-tight text-foreground">
              {project.name}
            </h1>
            {project.project_type && (
              <Badge variant="outline" className="text-xs">
                {typeLabels[project.project_type] || project.project_type}
              </Badge>
            )}
            {project.research_status && (
              <Badge
                variant={statusVariant[project.research_status] || 'secondary'}
                className="text-xs capitalize"
              >
                {project.research_status}
              </Badge>
            )}
          </div>

          {project.description && (
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-2xl line-clamp-2 sm:line-clamp-none">
              {project.description}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
            {project.deadline && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatRelativeDate(project.deadline)}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Created {new Date(project.created_at).toLocaleDateString()}
              {project.updated_at &&
                project.updated_at !== project.created_at && (
                  <span className="text-muted-foreground/70">
                    {' · last edited '}
                    {new Date(project.updated_at).toLocaleDateString()}
                  </span>
                )}
            </span>
          </div>

          {project.tags && project.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {project.tags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="text-xs font-normal"
                >
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
