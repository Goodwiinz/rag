'use client';

import type { ReactNode } from 'react';
import { BookOpen, FileText, Sparkles, StickyNote } from 'lucide-react';
import type { Project } from '@/services/projectService';

export type ProjectDetailTab =
  | 'documents'
  | 'notes'
  | 'bibliography'
  | 'drafts';

export interface ProjectDetailProps {
  project: Project;
  activeTab: ProjectDetailTab;
  onTabChange: (tab: ProjectDetailTab) => void;
  actions?: ReactNode;
  children: ReactNode;
}

const tabs: Array<{
  id: ProjectDetailTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'notes', label: 'Notes', icon: StickyNote },
  { id: 'bibliography', label: 'Bibliography', icon: BookOpen },
  { id: 'drafts', label: 'Drafts', icon: Sparkles },
];

export function ProjectDetail({
  project,
  activeTab,
  onTabChange,
  actions,
  children,
}: ProjectDetailProps) {
  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            {project.name}
          </h1>
          {project.description && (
            <p className="text-muted-foreground mt-2">{project.description}</p>
          )}
        </div>
        {actions}
      </div>

      <div
        role="tablist"
        className="flex items-center gap-1 mb-6 border-b border-border"
      >
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                selected
                  ? 'text-[var(--nous-sol-safe)] border-[var(--nous-sol-safe)]'
                  : 'text-muted-foreground border-transparent hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div>{children}</div>
    </div>
  );
}

export default ProjectDetail;
