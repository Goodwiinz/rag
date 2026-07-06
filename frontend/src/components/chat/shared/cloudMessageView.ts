import {
  MessageRole,
  type ChatMessage,
  type DbToolExecution,
} from '@/types/workspace';
import { normalizeCitation } from '@/utils/citationNormalizer';
import type { Citation } from '@/utils/citationParser';
import type { PlanStep } from '@/types/agent-chat';

/** A single agent tool execution captured during a streaming turn. */
export interface ActivityStep {
  tool: string;
  label: string;
  status: 'running' | 'done' | 'error';
  durationMs?: number;
  /** Compact one-line summary of the tool's arguments (e.g. the query). */
  argsSummary?: string;
  /** Compact one-line summary of the result, or the error text on failure. */
  resultSummary?: string;
}

const SUMMARY_MAX = 140;

function truncate(s: string): string {
  return s.length > SUMMARY_MAX ? s.slice(0, SUMMARY_MAX - 1) + '…' : s;
}

/** One-line `key: value` summary of tool-call args for the activity strip. */
export function summarizeToolArgs(
  args: Record<string, unknown> | undefined
): string | undefined {
  if (!args || typeof args !== 'object') return undefined;
  const entries = Object.entries(args).filter(([, v]) => v != null);
  if (entries.length === 0) return undefined;
  const joined = entries
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ');
  return truncate(joined);
}

/**
 * One-line summary of a tool result for the activity strip. Result payloads
 * are JSON strings; prefer their `message`/`error` field, fall back to the
 * truncated raw text.
 */
export function summarizeToolResult(
  result: string | undefined
): string | undefined {
  if (!result) return undefined;
  try {
    const parsed: unknown = JSON.parse(result);
    if (parsed && typeof parsed === 'object') {
      const obj = parsed as Record<string, unknown>;
      const msg = obj.error ?? obj.message ?? obj.summary;
      if (typeof msg === 'string' && msg.length > 0) return truncate(msg);
    }
  } catch {
    // not JSON — fall through to raw text
  }
  return truncate(result);
}

/**
 * Map persisted chat_messages.tool_executions rows onto the activity-strip
 * shape so a reloaded thread shows the same tool steps as the live turn.
 * Persisted rows are always settled: anything not failed reads as done.
 */
export function mapDbToolExecutions(
  execs: DbToolExecution[] | undefined
): ActivityStep[] | undefined {
  if (!execs || execs.length === 0) return undefined;
  return execs.map((e) => {
    const argsSummary = summarizeToolArgs(e.args);
    const resultSummary = e.error
      ? summarizeToolResult(e.error)
      : summarizeToolResult(
          typeof e.result === 'string' ? e.result : undefined
        );
    return {
      tool: e.tool_name,
      label: e.tool_display_name || e.tool_name,
      status: e.status === 'failed' || e.error ? 'error' : 'done',
      ...(typeof e.duration_ms === 'number'
        ? { durationMs: e.duration_ms }
        : {}),
      ...(argsSummary ? { argsSummary } : {}),
      ...(resultSummary ? { resultSummary } : {}),
    } satisfies ActivityStep;
  });
}

export interface ChatPageMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
  /** Tool executions recorded during the turn that produced this message. */
  toolExecutions?: ActivityStep[];
  /** Structured execution plan emitted by the agent planner for this turn. */
  plan?: PlanStep[];
  metadata?: {
    toolsUsed?: string[];
    responseTimeMs?: number;
    sourcesCount?: number;
    /** The user stopped this response mid-stream; the text is partial. */
    stopped?: boolean;
    /** Per-turn LLM token usage (persisted in chat_messages.token_usage). */
    tokenUsage?: { input: number; output: number };
  };
}

export function mapStoreMessagesToChatMessages(
  messages: ChatMessage[]
): ChatPageMessage[] {
  return messages.map((dbMsg) => {
    const hasMetadata = dbMsg.latency_ms || dbMsg.stopped || dbMsg.token_usage;
    return {
      id: dbMsg.id,
      role:
        dbMsg.role === MessageRole.USER
          ? ('user' as const)
          : ('assistant' as const),
      content: dbMsg.content,
      timestamp: new Date(dbMsg.created_at).getTime(),
      citations: dbMsg.citations?.map(normalizeCitation),
      toolExecutions: mapDbToolExecutions(dbMsg.tool_executions),
      ...(dbMsg.plan && dbMsg.plan.length > 0 ? { plan: dbMsg.plan } : {}),
      metadata: hasMetadata
        ? {
            ...(dbMsg.latency_ms ? { responseTimeMs: dbMsg.latency_ms } : {}),
            ...(dbMsg.stopped ? { stopped: true } : {}),
            ...(dbMsg.token_usage
              ? {
                  tokenUsage: {
                    input: dbMsg.token_usage.input_tokens,
                    output: dbMsg.token_usage.output_tokens,
                  },
                }
              : {}),
          }
        : undefined,
    };
  });
}

interface SelectDisplayedMessagesParams {
  localMessages: ChatPageMessage[];
  storeMessages?: ChatMessage[];
}

function shouldUseStoreMessages(
  localMessages: ChatPageMessage[],
  storeMessages: ChatMessage[]
): boolean {
  return (
    storeMessages.length > 0 && storeMessages.length >= localMessages.length
  );
}

/**
 * Carry in-memory turn provenance over to the server-mapped message.
 * plan / token_usage are persisted now, but the store page may have been
 * fetched BEFORE the assistant row landed (or the row predates the columns),
 * so when the displayed list flips from local to store messages after
 * `done`, the plan and token badge would silently vanish from the
 * just-finished turn. Server values stay canonical where both exist.
 */
function mergeLocalProvenance(
  mapped: ChatPageMessage[],
  localMessages: ChatPageMessage[]
): ChatPageMessage[] {
  if (localMessages.length === 0) return mapped;

  const localById = new Map(
    localMessages.filter((m) => m.id).map((m) => [m.id as string, m])
  );

  return mapped.map((message) => {
    // Prefer id reconciliation (the done payload backfills the persisted
    // id); fall back to role+content for optimistic messages without one.
    const local =
      (message.id ? localById.get(message.id) : undefined) ??
      localMessages.find(
        (l) => !l.id && l.role === message.role && l.content === message.content
      );
    if (!local) return message;

    const mergedMetadata =
      local.metadata || message.metadata
        ? { ...local.metadata, ...message.metadata }
        : undefined;

    return {
      ...message,
      ...((message.plan ?? local.plan)
        ? { plan: message.plan ?? local.plan }
        : {}),
      ...(mergedMetadata ? { metadata: mergedMetadata } : {}),
    };
  });
}

export function selectDisplayedMessages({
  localMessages,
  storeMessages = [],
}: SelectDisplayedMessagesParams): ChatPageMessage[] {
  if (shouldUseStoreMessages(localMessages, storeMessages)) {
    return mergeLocalProvenance(
      mapStoreMessagesToChatMessages(storeMessages),
      localMessages
    );
  }

  return localMessages;
}

interface ConversationWithMessages {
  id: string;
  messages: ChatPageMessage[];
  updatedAt: number;
  previewText?: string;
  messageCount?: number;
}

function messagesMatch(
  left: ChatPageMessage[],
  right: ChatPageMessage[]
): boolean {
  return (
    left.length === right.length &&
    left.every((message, index) => {
      const other = right[index];
      return (
        message.id === other?.id &&
        message.role === other?.role &&
        message.content === other?.content &&
        message.timestamp === other?.timestamp
      );
    })
  );
}

export function syncConversationMessagesWithStore<
  T extends ConversationWithMessages,
>(
  conversations: T[],
  threadId: string | null | undefined,
  storeMessages: ChatMessage[] = []
): T[] {
  if (!threadId || storeMessages.length === 0) {
    return conversations;
  }

  const mappedMessages = mapStoreMessagesToChatMessages(storeMessages);

  return conversations.map((conversation) => {
    if (conversation.id !== threadId) {
      return conversation;
    }

    // Don't clobber a fuller local cache with a partial store page — unless
    // the store's tail is strictly NEWER than the cached tail. After FIFO
    // eviction (chat-store MAX_CACHED_THREADS) a revisited thread reloads
    // with only the latest page, which can be shorter than the stale cache;
    // without the newer-tail escape this guard froze the sidebar cache on
    // the pre-eviction copy forever.
    const cachedTailTs =
      conversation.messages[conversation.messages.length - 1]?.timestamp ?? 0;
    const mappedTailTs =
      mappedMessages[mappedMessages.length - 1]?.timestamp ?? 0;
    if (
      mappedMessages.length < conversation.messages.length &&
      mappedTailTs <= cachedTailTs
    ) {
      return conversation;
    }

    if (messagesMatch(conversation.messages, mappedMessages)) {
      return conversation;
    }

    return {
      ...conversation,
      messages: mappedMessages,
      previewText: mappedMessages[mappedMessages.length - 1]?.content,
      messageCount: Math.max(
        conversation.messageCount ?? 0,
        mappedMessages.length
      ),
      updatedAt:
        mappedMessages[mappedMessages.length - 1]?.timestamp ??
        conversation.updatedAt,
    };
  });
}
