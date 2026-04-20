// nous-agent-status-card.tsx — Shows an agent mid-task with step progress.
import * as React from 'react';

export type AgentStepStatus = 'done' | 'active' | 'pending';

export interface AgentStep {
  label: string;
  status: AgentStepStatus;
}

export interface NousAgentStatusCardProps {
  name: string;
  task: string;
  steps: AgentStep[];
}

function dotStyle(status: AgentStepStatus): React.CSSProperties {
  switch (status) {
    case 'done':
      return { background: 'oklch(60% 0.14 150)' };
    case 'active':
      return { background: 'var(--nous-sol)' };
    case 'pending':
      return { background: 'var(--nous-border-2)' };
  }
}

export function NousAgentStatusCard({
  name,
  task,
  steps,
}: NousAgentStatusCardProps) {
  return (
    <div
      className="rounded-xl border p-5"
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'var(--nous-bg-2)',
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="grid h-9 w-9 place-items-center rounded-lg"
          style={{ background: 'var(--nous-aurum)' }}
          aria-hidden
        >
          <span
            className="nous-pulse h-2 w-2 rounded-full"
            style={{ background: 'var(--nous-sol)' }}
          />
        </div>
        <div>
          <div
            className="text-sm font-semibold"
            style={{
              fontFamily: 'var(--nous-font-ui)',
              color: 'var(--nous-fg-1)',
            }}
          >
            {name}
          </div>
          <div
            className="text-xs italic"
            style={{
              fontFamily: 'var(--nous-font-body)',
              color: 'var(--nous-fg-3)',
            }}
          >
            {task}
          </div>
        </div>
      </div>
      <ol
        className="mt-4 space-y-2 border-l pl-4"
        style={{ borderColor: 'var(--nous-border-1)' }}
      >
        {steps.map((step, i) => (
          <li
            key={`${step.label}-${i}`}
            className="flex items-center gap-2 text-sm"
            style={{
              fontFamily: 'var(--nous-font-body)',
              color: 'var(--nous-fg-2)',
            }}
          >
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                step.status === 'active' ? 'nous-pulse' : ''
              }`}
              style={dotStyle(step.status)}
              aria-hidden
            />
            <span
              style={
                step.status === 'done'
                  ? {
                      textDecoration: 'line-through',
                      color: 'var(--nous-fg-3)',
                    }
                  : undefined
              }
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
