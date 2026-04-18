'use client';

import type { ReactNode } from 'react';
import { BookOpen, FileText, Sparkles, StickyNote } from 'lucide-react';
import type { Project } from '@/services/projectService';

export type ProjectDetailTab = 'documents' | 'notes' | 'bibliography' | 'drafts';

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
          <h1 className="text-2xl font-mono font-bold text-[#00ff9f]">{project.name}</h1>
          {project.description && <p className="text-gray-400 mt-2">{project.description}</p>}
        </div>
        {actions}
      </div>

      <div className="flex items-center gap-1 mb-6 border-b border-[#1a1a1a]">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 font-mono text-sm border-b-2 transition-colors ${
                selected
                  ? 'text-[#00ff9f] border-[#00ff9f]'
                  : 'text-gray-500 border-transparent hover:text-gray-300'
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
