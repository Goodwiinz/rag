'use client';

import { memo, type ReactElement } from 'react';
import type { ToolCallMessagePartStatus } from '@assistant-ui/react';
import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';
import { toToolCallParts } from './convertMessage';

interface AuiToolPartsProps {
  messageId: string;
  steps: ActivityStep[];
  isStreaming: boolean;
}

/**
 * A 'running' step on a message that is no longer streaming never settled —
 * the turn was stopped or the stream dropped — so it reads as cancelled.
 */
function toPartStatus(
  status: ActivityStep['status'],
  isStreaming: boolean
): ToolCallMessagePartStatus {
  if (status === 'error') return { type: 'incomplete', reason: 'error' };
  if (status === 'running') {
    return isStreaming
      ? { type: 'running' }
      : { type: 'incomplete', reason: 'cancelled' };
  }
  return { type: 'complete' };
}

// HITL approvals stay on the existing interrupt/confirm flow in stage 1; we
// never emit a 'requires-action' status, so the approval bar (the only
// consumer of these callbacks) cannot render.
const noopHandlers = {
  addResult: () => undefined,
  resume: () => undefined,
  respondToApproval: () => undefined,
};

export const AuiToolParts = memo(function AuiToolParts({
  messageId,
  steps,
  isStreaming,
}: AuiToolPartsProps): ReactElement | null {
  if (steps.length === 0) return null;
  const parts = toToolCallParts(messageId, steps);
  return (
    <div data-slot="aui-tool-parts" className="flex flex-col gap-1 mb-2">
      {parts.map((part, i) => (
        <ToolFallback
          key={part.toolCallId}
          type="tool-call"
          toolCallId={part.toolCallId}
          toolName={part.toolName}
          args={part.args}
          argsText={part.argsText}
          result={part.result}
          status={toPartStatus(steps[i].status, isStreaming)}
          {...noopHandlers}
        />
      ))}
    </div>
  );
});
