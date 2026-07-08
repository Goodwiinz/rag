import type { ThreadMessageLike } from '@assistant-ui/react';

import type {
  ActivityStep,
  ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';
import type { MessageAttachment } from '@/types/workspace';

import { HITL_APPROVAL_TOOL } from './hitlBridge';

type ToolCallPart = {
  type: 'tool-call';
  toolCallId: string;
  toolName: string;
  // ThreadMessageLike types args as ReadonlyJSONObject. At runtime we carry the
  // structured (backend-redacted, JSON-safe) tool args so declarative per-tool
  // renderers read real fields via their own TArgs generic; the type stays the
  // JSON-compatible empty shape. `argsText` is the one-line fallback summary.
  args: Record<string, never>;
  argsText: string;
  result?: string;
  isError?: true;
};

// Tool parts must be referentially stable across per-token re-conversions of
// the in-flight message: streamingSteps only changes reference on
// tool_start/tool_end, so a WeakMap keyed on the steps array is exact.
const partsCache = new WeakMap<ActivityStep[], ToolCallPart[]>();

function getAttachmentName(attachment: MessageAttachment): string {
  return (
    attachment.display_name ??
    attachment.document_title ??
    attachment.document_id ??
    'Attachment'
  );
}

function getAttachmentType(
  attachment: MessageAttachment
): 'image' | 'document' | 'file' {
  if (attachment.mime_type?.startsWith('image/') || attachment.thumbnail_url) {
    return 'image';
  }
  if (attachment.document_type || attachment.mime_type?.includes('pdf')) {
    return 'document';
  }
  return 'file';
}

function toRuntimeAttachments(
  attachments: MessageAttachment[] | undefined
): ThreadMessageLike['attachments'] {
  if (!attachments || attachments.length === 0) return undefined;

  return attachments.map((attachment) => {
    const name = getAttachmentName(attachment);
    const type = getAttachmentType(attachment);
    return {
      id: attachment.id,
      type,
      name,
      ...(attachment.mime_type ? { contentType: attachment.mime_type } : {}),
      status: { type: 'complete' as const },
      content:
        type === 'image' && attachment.thumbnail_url
          ? [
              {
                type: 'image' as const,
                image: attachment.thumbnail_url,
                filename: name,
              },
            ]
          : [],
    };
  });
}

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
      args: (step.args ?? {}) as Record<string, never>,
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

  // In-band HITL approval gate (AUI_FULL / P4): emit an approval tool-call part
  // routed to the registered HitlApprovalToolUI. Its args carry the confirmed
  // tool name + args for display; the bridge store drives resolution.
  const approvalParts: ToolCallPart[] = message.pendingApproval
    ? [
        {
          type: 'tool-call',
          toolCallId: `${message.id ?? message.timestamp}-approval`,
          toolName: HITL_APPROVAL_TOOL,
          args: {
            toolName: message.pendingApproval.toolName,
            toolArgs: message.pendingApproval.args,
          } as unknown as Record<string, never>,
          argsText: '',
        },
      ]
    : [];
  return {
    id: message.id,
    role: message.role,
    // Null-safe: a message may not have a timestamp yet (e.g. an optimistic
    // local insert before the server round-trip). `new Date(0)` would be a
    // misleading 1970 date, so omit createdAt instead.
    ...(message.timestamp ? { createdAt: new Date(message.timestamp) } : {}),
    ...(message.role === 'assistant' && message.content
      ? { status: { type: 'complete' as const, reason: 'stop' as const } }
      : {}),
    ...(message.attachments?.length
      ? { attachments: toRuntimeAttachments(message.attachments) }
      : {}),
    content: [
      ...toolParts,
      ...approvalParts,
      { type: 'text', text: message.content },
    ],
  };
}
