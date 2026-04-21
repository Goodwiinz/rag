'use client';

import { cn } from '@/lib/utils';
import { AgentActivityPanel } from './AgentActivityPanel';
import { AllCitationsPanel } from './AllCitationsPanel';
import { ContextPanel } from './ContextPanel';
import { ProgressPanel } from './ProgressPanel';
import { RelatedResultsPanel } from './RelatedResultsPanel';
import { WorkingFoldersPanel } from './WorkingFoldersPanel';

interface ContextRailProps {
  threadId: string | null;
  ragEnabled?: boolean;
  workspaceName?: string | null;
  className?: string;
}

export function ContextRail({
  threadId,
  ragEnabled,
  workspaceName,
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
      <WorkingFoldersPanel workspaceName={workspaceName} />
      <AgentActivityPanel threadId={threadId} />
      <RelatedResultsPanel />
      <AllCitationsPanel />
      <ContextPanel ragEnabled={ragEnabled} workspaceName={workspaceName} />
    </aside>
  );
}
