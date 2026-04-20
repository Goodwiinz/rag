'use client';

import * as React from 'react';
import { NousAgentStatusCard, type AgentStep } from '@/nous';
import { useAgentActivityStore, type Step } from '@/stores/agentActivityStore';

interface AgentActivityPanelProps {
  threadId: string | null;
}

function toAgentStep(step: Step): AgentStep {
  return {
    label: step.label,
    status:
      step.status === 'done'
        ? 'done'
        : step.status === 'error'
          ? 'done'
          : 'active',
  };
}

export function AgentActivityPanel({ threadId }: AgentActivityPanelProps) {
  const run = useAgentActivityStore((s) =>
    threadId ? s.runs[threadId] : undefined
  );

  if (!run) return null;

  return (
    <section aria-label="Agent activity">
      <div
        className="text-[10px] uppercase tracking-wider mb-2 px-1"
        style={{
          color: 'var(--nous-fg-3)',
          fontFamily: 'var(--nous-font-ui)',
        }}
      >
        Agent Activity
      </div>
      <NousAgentStatusCard
        name={run.name}
        task={run.task}
        steps={run.steps.map(toAgentStep)}
      />
    </section>
  );
}
