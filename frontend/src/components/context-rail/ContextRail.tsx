'use client';

import { cn } from '@/lib/utils';
import { AgentActivityPanel } from './AgentActivityPanel';
import { AllCitationsPanel } from './AllCitationsPanel';
import { ContextPanel } from './ContextPanel';
import { ProgressPanel } from './ProgressPanel';
import { RelatedResultsPanel } from './RelatedResultsPanel';
import {
  WorkingFoldersPanel,
  type WorkingFoldersSelection,
} from './WorkingFoldersPanel';

interface ContextRailProps {
  threadId: string | null;
  ragEnabled?: boolean;
  workspaceName?: string | null;
  projectId?: string;
  onSelect?: (node: WorkingFoldersSelection) => void;
  className?: string;
}

export function ContextRail({
  threadId,
  ragEnabled,
  workspaceName,
  projectId,
  onSelect,
  className,
}: ContextRailProps) {
  return (
    <aside
      className={cn(
        'flex flex-col gap-4 overflow-y-auto px-4 py-4',
        className
      )}
      style={{
        background: 'var(--nous-bg-1)',
        fontFamily: 'var(--nous-font-ui)',
      }}
      aria-label="Chat context rail"
    >
      <ProgressPanel threadId={threadId} />
      <WorkingFoldersPanel
        projectId={projectId}
        workspaceName={workspaceName}
        onSelect={onSelect}
      />
      <AgentActivityPanel threadId={threadId} />
      <RelatedResultsPanel />
      <AllCitationsPanel />
      <ContextPanel ragEnabled={ragEnabled} workspaceName={workspaceName} />
    </aside>
  );
}
