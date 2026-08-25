'use client';

import { NousAgentStatusCard, type AgentStep } from '@/nous';
import { useAgentActivityStore, type Step } from '@/stores/agentActivityStore';
import { toolStatusLabel } from './toolLabels';
import { CollapsibleCard } from './CollapsibleCard';

interface AgentActivityPanelProps {
  threadId: string | null;
}

function toAgentStep(step: Step): AgentStep {
  return {
    label: toolStatusLabel(step.tool, step.status),
    status: step.status,
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
        active={run.state === 'running'}
      />
    </CollapsibleCard>
  );
}
