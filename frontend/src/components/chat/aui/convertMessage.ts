import type { ThreadMessageLike } from '@assistant-ui/react';

import type {
  ActivityStep,
  ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';

type ToolCallPart = {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  // ThreadMessageLike requires args to be a ReadonlyJSONObject; we never have
  // structured args (only argsSummary text), so this is always the empty object.
  args: Record<string, never>;
  argsText: string;
  result?: string;
  isError?: true;
};

// Tool parts must be referentially stable across per-token re-conversions of
// the in-flight message: streamingSteps only changes reference on
// tool_start/tool_end, so a WeakMap keyed on the steps array is exact.
const partsCache = new WeakMap<ActivityStep[], ToolCallPart[]>();

export function toToolCallParts(
  messageId: string,
  steps: ActivityStep[]
): ToolCallPart[] {
  const cached = partsCache.get(steps);
  if (cached) return cached;
  const parts = steps.map((step, i): ToolCallPart => {
    const settled = step.status !== 'running';
    return {
      type: 'tool-call',
      toolCallId: `${messageId}-tool-${i}`,
      toolName: step.tool,
      args: {},
      argsText: step.argsSummary ?? '',
      ...(settled && step.resultSummary !== undefined
        ? { result: step.resultSummary }
        : {}),
      ...(step.status === 'error' ? { isError: true as const } : {}),
    };
  });
  partsCache.set(steps, parts);
  return parts;
}

export function convertMessage(message: ChatPageMessage): ThreadMessageLike {
  const toolParts = message.toolExecutions?.length
    ? // Deterministic per-message fallback: a shared constant like 'local'
      // would collide across multiple id-less messages (duplicate toolCallIds).
      toToolCallParts(
        message.id ?? String(message.timestamp),
        message.toolExecutions
      )
    : [];
  return {
    id: message.id,
    role: message.role,
    // Null-safe: a message may not have a timestamp yet (e.g. an optimistic
    // local insert before the server round-trip). `new Date(0)` would be a
    // misleading 1970 date, so omit createdAt instead.
    ...(message.timestamp ? { createdAt: new Date(message.timestamp) } : {}),
    content: [...toolParts, { type: 'text', text: message.content }],
  };
}
