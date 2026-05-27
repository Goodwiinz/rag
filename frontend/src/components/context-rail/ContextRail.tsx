'use client';

import { cn } from '@/lib/utils';
import { AgentActivityPanel } from './AgentActivityPanel';
import { AllCitationsPanel } from './AllCitationsPanel';
import { ContextPanel } from './ContextPanel';
import { ProgressPanel } from './ProgressPanel';
import { ProjectBindingCard } from './ProjectBindingCard';
import { RelatedResultsPanel } from './RelatedResultsPanel';
import {
  WorkingFoldersPanel,
  type WorkingFoldersSelection,
} from './WorkingFoldersPanel';

interface ContextRailProps {
  threadId: string | null;
  ragEnabled?: boolean;
  workspaceName?: string | null;
  workspaceId?: string;
  projectId?: string;
  projectName?: string | null;
  projectFileCount?: number;
  onSelect?: (node: WorkingFoldersSelection) => void;
  onProjectBound?: (projectId: string, projectName: string) => void;
  className?: string;
}

export function ContextRail({
  threadId,
  ragEnabled,
  workspaceName,
  workspaceId,
  projectId,
  projectName,
  projectFileCount,
  onSelect,
  onProjectBound,
  className,
}: ContextRailProps) {
  const threadLabel = threadId ? `thread · ${threadId.slice(0, 8)}` : null;

  return (
    <aside
      className={cn(
        'flex flex-col gap-3 overflow-y-auto px-3 py-3 bg-[var(--nous-bg-1)]',
        className
      )}
      aria-label="Chat context rail"
    >
      <ProjectBindingCard
        projectId={projectId}
        projectName={projectName}
        workspaceName={workspaceName}
        fileCount={projectFileCount}
        threadLabel={threadLabel}
        threadId={threadId}
        workspaceId={workspaceId}
        onProjectBound={onProjectBound}
      />
      <WorkingFoldersPanel
        projectId={projectId}
        workspaceName={workspaceName}
        onSelect={onSelect}
      />
      <AgentActivityPanel threadId={threadId} />
      <ProgressPanel threadId={threadId} />
      <RelatedResultsPanel />
      <AllCitationsPanel />
      <ContextPanel ragEnabled={ragEnabled} workspaceName={workspaceName} />
    </aside>
  );
}
