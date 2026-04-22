'use client';

import { NousAgentStatusCard, type AgentStep } from '@/nous';
import { useAgentActivityStore, type Step } from '@/stores/agentActivityStore';
import { CollapsibleCard } from './CollapsibleCard';

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

  if (!run || run.steps.length === 0) return null;

  return (
    <CollapsibleCard title="Agent activity">
      <NousAgentStatusCard
        name={run.name}
        task={run.task}
        steps={run.steps.map(toAgentStep)}
      />
    </CollapsibleCard>
  );
}
