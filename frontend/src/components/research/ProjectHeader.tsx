'use client';

import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  FileText,
  BookOpen,
  StickyNote,
  Sparkles,
  Calendar,
  Clock,
} from 'lucide-react';
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

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-4 py-3">
      <div className="text-muted-foreground">{icon}</div>
      <div>
        <p className="text-lg font-semibold text-foreground">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  const router = useRouter();

  return (
    <div className="mb-8 space-y-4">
      {/* Back link */}
      <button
        onClick={() => router.push('/projects')}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Projects
      </button>

      {/* Hero card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          {/* Left: Title + metadata */}
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                {project.name}
              </h1>
              {project.project_type && (
                <Badge variant="outline" className="text-xs">
                  {typeLabels[project.project_type] || project.project_type}
                </Badge>
              )}
              {project.research_status && (
                <Badge
                  variant={
                    statusVariant[project.research_status] || 'secondary'
                  }
                  className="text-xs capitalize"
                >
                  {project.research_status}
                </Badge>
              )}
            </div>

            {project.description && (
              <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
                {project.description}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {project.deadline && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {formatRelativeDate(project.deadline)}
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Created {new Date(project.created_at).toLocaleDateString()}
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

          {/* Right: Stats grid */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 shrink-0">
            <StatCard
              icon={<FileText className="h-4 w-4" />}
              label="Documents"
              value={project.document_count || 0}
            />
            <StatCard
              icon={<BookOpen className="h-4 w-4" />}
              label="Citations"
              value={project.citation_count || 0}
            />
            <StatCard
              icon={<StickyNote className="h-4 w-4" />}
              label="Notes"
              value={project.note_count || 0}
            />
            <StatCard
              icon={<Sparkles className="h-4 w-4" />}
              label="Drafts"
              value={project.draft_count || 0}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
