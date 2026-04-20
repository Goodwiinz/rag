'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { AgentActivityPanel } from './AgentActivityPanel';
import { RelatedResultsPanel } from './RelatedResultsPanel';
import { AllCitationsPanel } from './AllCitationsPanel';

interface ContextRailProps {
  threadId: string | null;
  className?: string;
}

export function ContextRail({ threadId, className }: ContextRailProps) {
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
      <AgentActivityPanel threadId={threadId} />
      <RelatedResultsPanel />
      <AllCitationsPanel />
    </aside>
  );
}
