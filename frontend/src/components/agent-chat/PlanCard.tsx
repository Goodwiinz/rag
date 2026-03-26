'use client';

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Circle,
  Loader2,
  CheckCircle2,
  ListChecks,
} from 'lucide-react';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';

type StepStatus = 'pending' | 'active' | 'done';

interface PlanCardProps {
  steps: PlanStep[];
  /** Currently active tool executions to derive step status */
  toolExecutions?: ToolExecution[];
}

function deriveStepStatus(
  step: PlanStep,
  toolExecutions: ToolExecution[]
): StepStatus {
  const matching = toolExecutions.filter((te) => te.toolName === step.tool);
  if (matching.length === 0) return 'pending';
  const hasRunning = matching.some((te) => te.status === 'running');
  if (hasRunning) return 'active';
  const hasCompleted = matching.some((te) => te.status === 'completed');
  if (hasCompleted) return 'done';
  return 'pending';
}

function StepStatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case 'active':
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-[#D4A039]" />;
    case 'done':
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />;
    case 'pending':
    default:
      return <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />;
  }
}

export function PlanCard({ steps, toolExecutions = [] }: PlanCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const doneCount = steps.filter(
    (s) => deriveStepStatus(s, toolExecutions) === 'done'
  ).length;
  const totalCount = steps.length;

  return (
    <div className="border border-border/50 rounded-lg bg-[#0A0A0E]/50 text-xs my-2 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/20 cursor-pointer transition-colors"
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} execution plan`}
      >
        <ListChecks className="h-3.5 w-3.5 text-[#D4A039]" />
        <span className="text-[#F7F7F5] font-medium">Execution Plan</span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          <span className="text-muted-foreground/70 tabular-nums text-[10px]">
            {doneCount}/{totalCount}
          </span>
          {isExpanded ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground/60" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
          )}
        </span>
      </button>

      {/* Steps list */}
      {isExpanded && (
        <div className="border-t border-border/30 px-3 py-2 space-y-1.5">
          {steps.map((step) => {
            const status = deriveStepStatus(step, toolExecutions);
            return (
              <div
                key={step.step}
                className={`flex items-start gap-2 py-1 ${
                  status === 'active'
                    ? 'text-[#F7F7F5]'
                    : status === 'done'
                      ? 'text-muted-foreground/70'
                      : 'text-muted-foreground/50'
                }`}
              >
                <span className="mt-0.5 shrink-0">
                  <StepStatusIcon status={status} />
                </span>
                <span className="flex-1 leading-relaxed">
                  <span className="font-medium">{step.step}.</span>{' '}
                  {step.description}
                  <span className="ml-1.5 text-[10px] text-[#D4A039]/70 font-mono">
                    {step.tool}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
