'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';
import {
  ActionBarPrimitive,
  ErrorPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useThread,
} from '@assistant-ui/react';
import {
  AlertTriangle,
  Check,
  Copy,
  FileText,
  Image as ImageIcon,
  Pencil,
  RotateCcw,
  X,
} from 'lucide-react';

import { motion, useReducedMotion } from 'framer-motion';

import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { CitationRenderer } from '@/components/chat/CitationRenderer';
import { ChatInlinePlan } from '@/components/chat/shared/ChatInlinePlan';
import { CitationChips } from '@/components/chat/shared/CitationChips';
import { formatStreamingElapsed } from '@/components/chat/shared/formatStreamingElapsed';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import { MessageFeedback } from '@/components/chat/shared/MessageFeedback';
import { ThinkingMatrix } from '@/components/chat/shared/ThinkingMatrix';
import { AuiToolParts } from '@/components/chat/aui/AuiToolParts';
import {
  ToolStrip,
  getToolStripProps,
} from '@/components/chat/shared/ToolStrip';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { completeStreamingMarkdown } from '@/lib/markdown-utils';
import { cn } from '@/lib/utils';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { getReferencedCitations, type Citation } from '@/utils/citationParser';

export type OnCitationClick = (
  citations: Citation[],
  clickedCitation: Citation,
  traceId?: string
) => void;

function TextPart({ className }: { className?: string }): ReactElement {
  return (
    <p
      className={cn(
        'whitespace-pre-wrap text-[14px] leading-relaxed',
        className
      )}
    >
      <MessagePartPrimitive.Text />
      <MessagePartPrimitive.InProgress>
        <span
          className="ml-0.5 inline-block h-4 w-[3px] rounded-sm align-text-bottom animate-pulse bg-(--nous-sol) dark:bg-(--nous-helios)"
          data-testid="streaming-cursor"
        />
      </MessagePartPrimitive.InProgress>
    </p>
  );
}

function ImagePart(): ReactElement {
  return (
    <MessagePartPrimitive.Image className="max-h-72 max-w-full rounded-xl border border-(--nous-border-1) object-contain" />
  );
}

function FilePart({ filename }: { filename?: string }): ReactElement {
  return (
    <div className="inline-flex max-w-full items-center gap-2 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2) px-3 py-2 text-sm text-(--nous-fg-1)">
      <FileText className="h-4 w-4 shrink-0 text-(--nous-fg-3)" />
      <span className="truncate">{filename ?? 'File attachment'}</span>
    </div>
  );
}

function MessageParts({
  assistant,
  assistantText,
}: {
  assistant?: boolean;
  /** When provided, replaces the plain text part for assistant messages —
   * used to route committed content through CitationRenderer (markdown +
   * clickable inline citations) instead of raw MessagePartPrimitive.Text. */
  assistantText?: ReactNode;
}): ReactElement {
  return (
    <MessagePrimitive.Parts>
      {({ part }) => {
        switch (part.type) {
          case 'text':
            if (assistant && assistantText !== undefined) {
              return <>{assistantText}</>;
            }
            return (
              <TextPart className={assistant ? 'font-serif' : undefined} />
            );
          case 'image':
            return <ImagePart />;
          case 'file':
            return <FilePart filename={part.filename} />;
          case 'tool-call':
            return part.toolUI ?? <ToolFallback {...part} />;
          case 'data':
            return part.dataRendererUI ?? null;
          default:
            return null;
        }
      }}
    </MessagePrimitive.Parts>
  );
}

function AttachmentBadge({ type }: { type: string }): ReactElement {
  if (type === 'image') {
    return <ImageIcon className="h-3.5 w-3.5 text-(--nous-fg-3)" />;
  }

  return (
    <span className="rounded bg-(--nous-aurum) px-1.5 py-0.5 text-[10px] font-semibold uppercase text-(--nous-sol-safe) dark:bg-(--nous-ember) dark:text-(--nous-helios)">
      {type === 'document' ? 'PDF' : 'File'}
    </span>
  );
}

function MessageAttachments(): ReactElement {
  return (
    <MessagePrimitive.Attachments>
      {({ attachment }) => {
        const imageSrc = attachment.content?.find(
          (part) => part.type === 'image'
        )?.image;

        if (attachment.type === 'image' && imageSrc) {
          return (
            <img
              src={imageSrc}
              alt={attachment.name}
              className="mb-2 max-h-64 max-w-xs rounded-xl border border-(--nous-border-1) object-contain"
            />
          );
        }

        return (
          <div className="mb-2 inline-flex max-w-xs items-center gap-2 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2) px-3 py-2 text-sm text-(--nous-fg-1)">
            <AttachmentBadge type={attachment.type} />
            <span className="truncate">{attachment.name}</span>
          </div>
        );
      }}
    </MessagePrimitive.Attachments>
  );
}

function MessageError(): ReactElement {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root
        className="mt-2 rounded-md border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive"
        role="alert"
      >
        <ErrorPrimitive.Message />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
}

function MessageActions({
  assistant,
  onRetry,
  retryDisabled,
  onEdit,
  editButtonRef,
}: {
  assistant?: boolean;
  onRetry?: () => void;
  /** True while a regenerate cannot be accepted (a turn is in flight). */
  retryDisabled?: boolean;
  /** Enter edit-and-resend mode for a user message (user messages only). */
  onEdit?: () => void;
  /** Focus target the inline editor returns to on cancel/save. */
  editButtonRef?: React.Ref<HTMLButtonElement>;
}): ReactElement {
  return (
    <ActionBarPrimitive.Root
      data-slot="aui-message-actions"
      data-aui-autohide="always"
      autohide="always"
      autohideFloat="single-branch"
      hideWhenRunning
      className={cn('nous-msg-actions', !assistant && 'justify-end')}
    >
      <ActionBarPrimitive.Copy
        className="nous-msg-action"
        aria-label={assistant ? 'Copy assistant message' : 'Copy user message'}
        title="Copy message"
      >
        {/* The action confirms itself rather than relying on a toast. */}
        <MessagePrimitive.If copied={false}>
          <Copy className="h-3.5 w-3.5" />
        </MessagePrimitive.If>
        <MessagePrimitive.If copied>
          <Check className="h-3.5 w-3.5 text-(--nous-terra)" />
        </MessagePrimitive.If>
      </ActionBarPrimitive.Copy>
      {!assistant && onEdit ? (
        <button
          type="button"
          ref={editButtonRef}
          onClick={onEdit}
          className="nous-msg-action"
          aria-label="Edit and resend"
          title="Edit and resend"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
      ) : null}
      {assistant && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          disabled={retryDisabled}
          className="nous-msg-action"
          aria-label="Regenerate response"
          title={retryDisabled ? RETRY_UNAVAILABLE_REASON : 'Regenerate response'}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      ) : assistant ? (
        <ActionBarPrimitive.Reload
          className="nous-msg-action"
          aria-label="Regenerate response"
          title="Regenerate response"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </ActionBarPrimitive.Reload>
      ) : null}
    </ActionBarPrimitive.Root>
  );
}

export const EDIT_UNAVAILABLE_REASON =
  'Wait for the current response to finish';

export const RETRY_UNAVAILABLE_REASON =
  'Wait for the current response to finish';

export function AuiUserMessage({
  message,
  onEdit,
  editDisabled = false,
}: {
  /** Source ChatPageMessage — needed to seed the editor with the original
   * text and to gate the edit affordance off while a turn is streaming. */
  message?: ChatPageMessage;
  /** Edit-and-resend handler. When omitted (e.g. plain AuiMessages usage) the
   * edit affordance is hidden. */
  onEdit?: (newContent: string) => void;
  /** True while the session cannot accept a resend (a turn is in flight).
   * The editor stays OPEN and disables Save rather than closing on a save the
   * caller would silently drop — the draft must never vanish without a word. */
  editDisabled?: boolean;
}): ReactElement {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const wasEditingRef = useRef(false);
  // Set by saveEdit so the focus-restore effect can tell a SAVE exit from a
  // cancel/Escape exit — the two need different landing targets (below).
  const savedRef = useRef(false);

  const canEdit =
    !!onEdit && !!message?.content && !message?.isStreaming && !editing;

  const canSubmitEdit = !editDisabled && !!draft.trim();

  // Leaving edit mode unmounts the focused textarea; without this, focus drops
  // to <body> (Escape/cancel/save) and keyboard users lose their place.
  // On cancel/Escape the edit trigger is the precise target and it stays
  // mounted. On SAVE the resend starts immediately and the action bar hides
  // its buttons while the turn runs, so focusing the trigger is transient —
  // it unmounts a frame later and focus falls to <body> anyway. The message
  // container (tabIndex -1) persists across the resend, so save lands there.
  useEffect(() => {
    if (wasEditingRef.current && !editing) {
      const target = savedRef.current
        ? (containerRef.current ?? editButtonRef.current)
        : (editButtonRef.current ?? containerRef.current);
      target?.focus();
      savedRef.current = false;
    }
    wasEditingRef.current = editing;
  }, [editing]);

  const startEdit = (): void => {
    setDraft(message?.content ?? '');
    setEditing(true);
  };

  const cancelEdit = (): void => setEditing(false);

  const saveEdit = (): void => {
    const next = draft.trim();
    if (!next || editDisabled) return;
    savedRef.current = true;
    setEditing(false);
    onEdit?.(next);
  };

  return (
    <MessagePrimitive.Root
      data-role="user"
      className="group relative mb-7 flex justify-end sm:mb-8"
    >
      <div className="min-w-0 text-right" ref={containerRef} tabIndex={-1}>
        {editing ? (
          <div className="nous-bubble-user relative inline-block w-full max-w-[92%] px-4 py-2.5 text-left sm:max-w-[540px]">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                // isComposing guards IME input (Japanese/Chinese/Korean):
                // Enter confirms a candidate rather than submitting, and
                // preventDefault would break the composition itself.
                if (
                  e.key === 'Enter' &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  saveEdit();
                } else if (e.key === 'Escape') {
                  e.preventDefault();
                  cancelEdit();
                }
              }}
              aria-label="Edit your message"
              rows={Math.min(8, Math.max(2, draft.split('\n').length))}
              autoFocus
              className="w-full resize-none rounded-md border border-(--nous-border-1) bg-(--nous-bg-1) px-2 py-1 text-[14px] leading-relaxed text-(--nous-fg-1) focus:outline-none focus-visible:ring-2 focus-visible:ring-(--nous-sol)"
            />
            {editDisabled ? (
              <p
                role="note"
                className="mt-1.5 text-[11px] text-(--nous-fg-3)"
                data-testid="edit-unavailable-reason"
              >
                {EDIT_UNAVAILABLE_REASON}
              </p>
            ) : null}
            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={cancelEdit}
                className="inline-flex items-center gap-1 rounded-md border border-(--nous-border-1) px-2.5 py-1 text-[11px] font-medium text-(--nous-fg-2) hover:bg-(--nous-bg-2)"
              >
                <X className="h-3 w-3" />
                Cancel
              </button>
              <button
                type="button"
                onClick={saveEdit}
                disabled={!canSubmitEdit}
                aria-disabled={!canSubmitEdit}
                title={editDisabled ? EDIT_UNAVAILABLE_REASON : undefined}
                className="inline-flex items-center gap-1 rounded-md bg-(--nous-sol) px-2.5 py-1 text-[11px] font-semibold text-(--nous-erebus) hover:opacity-90 disabled:opacity-50"
              >
                <Check className="h-3 w-3" />
                Save &amp; resend
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="nous-bubble-user relative inline-block max-w-[92%] px-4 py-2.5 text-left transition-shadow hover:shadow-md sm:max-w-[540px]">
              <MessageAttachments />
              <div className="nous-chat-body">
                <MessageParts />
              </div>
              <MessageError />
            </div>
            <MessageActions
              onEdit={canEdit ? startEdit : undefined}
              editButtonRef={editButtonRef}
            />
          </>
        )}
      </div>
    </MessagePrimitive.Root>
  );
}

// Re-exported so existing `from '../AuiMessage'` test imports keep working —
// the implementation now lives in shared/formatStreamingElapsed.ts (moving it
// INTO ChatInlinePlan, which this file imports, would create an import cycle).
export { formatStreamingElapsed };

/** Pre-first-token status pill (mirrors the legacy ChatBubble ThinkingPill). */
function StreamingThinkingPill({
  label,
  elapsedMs,
}: {
  label: string;
  /** Last `heartbeat` reading for this turn (ms), or null before the first. */
  elapsedMs?: number | null;
}): ReactElement {
  const reduce = useReducedMotion();
  const elapsed = formatStreamingElapsed(elapsedMs ?? null);
  return (
    <motion.div
      className="nous-streaming-pill"
      role="status"
      aria-live="polite"
      initial={reduce ? false : { opacity: 0, y: 2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
    >
      <ThinkingMatrix />
      <span>{label}</span>
      {elapsed && (
        // aria-live off: the pill's own polite region announces the phase
        // label; a per-tick reading of the counter would just interrupt.
        <span aria-live="off" style={{ color: 'var(--nous-fg-2)' }}>
          · {elapsed}
        </span>
      )}
    </motion.div>
  );
}

/**
 * Live in-flight execution plan. A separate component (rather than reading
 * `streamingPlan` inside AuiStreamingBody directly) so its own store
 * subscription doesn't widen AuiStreamingBody's re-render surface.
 */
function StreamingPlanSection(): ReactElement | null {
  const streamingPlan = useChatStore((s) => s.streamingPlan);
  const streamingSteps = useChatStore((s) => s.streamingSteps);
  if (streamingPlan.length === 0) return null;
  return (
    <ChatInlinePlan
      plan={streamingPlan}
      toolExecutions={streamingSteps}
      streaming
    />
  );
}

/**
 * Body of the in-flight assistant turn path. The message itself is
 * a stable placeholder in the transcript; its live text/steps/citations are
 * read from the streaming store here, so token updates re-render only this
 * component (a store-selector subscription) and never remount the message row.
 * Faithfully mirrors the render the legacy streaming ChatBubble produced.
 */
function AuiStreamingBody(): ReactElement {
  const content = useChatStore((s) => s.streamingContent);
  const steps = useChatStore((s) => s.streamingSteps);
  const isRetrievingRag = useChatStore((s) => s.isRetrievingRag);
  const elapsedMs = useChatStore((s) => s.streamingElapsedMs);
  const streamingPhase = useChatStore((s) => s.streamingPhase);
  const streamingCitations = useChatStore((s) => s.streamingCitations);
  const threadId = useAgentActivityStore((s) => s.currentThreadId);
  const phaseLabel = streamingPhase
    ? {
        accepted: 'Starting',
        routing: 'Choosing approach',
        retrieving: 'Reading sources',
        planning: 'Planning',
        writing: 'Writing',
        finalizing: 'Saving response',
      }[streamingPhase]
    : undefined;
  const thinkingLabel =
    phaseLabel ?? (isRetrievingRag ? 'Reading sources' : 'Reflecting');

  return (
    <>
      <InlineAgentSummary threadId={threadId} />
      <StreamingPlanSection />
      {streamingCitations.length > 0 && (
        <div
          role="status"
          aria-live="polite"
          className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-nous-mono text-[10px]"
          style={{
            color: 'var(--nous-fg-2)',
            backgroundColor: 'var(--nous-bg-2)',
            borderColor: 'var(--nous-border-1)',
          }}
        >
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: 'var(--nous-sol)' }}
          />
          Reading {streamingCitations.length}{' '}
          {streamingCitations.length === 1 ? 'source' : 'sources'}
        </div>
      )}
      {steps.length > 0 && (
        <AuiToolParts messageId="streaming" steps={steps} isStreaming />
      )}
      {!content ? (
        <StreamingThinkingPill label={thinkingLabel} elapsedMs={elapsedMs} />
      ) : (
        <div className="nous-chat-body">
          <CitationRenderer
            content={completeStreamingMarkdown(content)}
            freshTail
            citations={[]}
            onCitationClick={() => {}}
          />
          <span
            className="ml-0.5 inline-block h-4 w-[3px] rounded-sm align-text-bottom animate-pulse bg-(--nous-sol) dark:bg-(--nous-helios)"
            data-testid="streaming-cursor"
          />
        </div>
      )}
    </>
  );
}

/**
 * Short, honest helper line under an error message, keyed by the SERVER's
 * `category` (see `AgentErrorCategory` in services/agentStreamEvents.ts).
 *
 * The category was write-only until now — recorded on the bubble and never
 * read. Anything absent or unrecognised falls back to the existing behaviour
 * (render `message.content`, the raw failure text), so an unknown category from
 * a newer backend degrades quietly instead of blanking the line.
 */
const ERROR_CATEGORY_HELP: Readonly<Record<string, string>> = {
  rate_limited: 'The service is busy — try again in a moment.',
  upstream_timeout: 'The model took too long. Retry usually works.',
  invalid_request: "This request can't be retried as-is.",
  conflict: 'A confirmation is already in progress.',
};

/**
 * Categories where an identical retry cannot succeed: the request itself is
 * rejected, or another confirmation already holds the claim. Offering Retry
 * there is a button that is guaranteed to fail — worse than no button.
 */
const NON_RETRYABLE_ERROR_CATEGORIES: ReadonlySet<string> = new Set([
  'invalid_request',
  'conflict',
]);

export function AuiAssistantMessage({
  message,
  onRetry,
  retryDisabled,
  onCitationClick,
}: {
  /** Source ChatPageMessage for the committed turn. Drives the provenance
   * chrome the legacy ChatBubble rendered: plan, tool strip (incl. token
   * usage), markdown + inline citations, and citation footer chips. When
   * absent (e.g. plain AuiMessages usage), falls back to primitive text. */
  message?: ChatPageMessage;
  onRetry?: () => void;
  /** True while a regenerate cannot be accepted (a turn is in flight). */
  retryDisabled?: boolean;
  onCitationClick?: OnCitationClick;
}): ReactElement {
  const allCitations = useMemo(
    () => message?.citations ?? [],
    [message?.citations]
  );

  const inlineCitations = useMemo(
    () => getReferencedCitations(message?.content ?? '', allCitations),
    [message?.content, allCitations]
  );

  // Inline-referenced citations when available, else all attached ones —
  // footer chips + tool strip must render whenever the backend attached
  // sources, even if the AI didn't use [Doc N] markers.
  const visibleCitations =
    inlineCitations.length > 0 ? inlineCitations : allCitations;

  const assistantText = message ? (
    // Committed assistant prose is quotable (see QuoteToolbar). Streaming
    // content is deliberately excluded — the text is still moving.
    <div data-quotable>
    <CitationRenderer
      content={message.content}
      citations={allCitations}
      onCitationClick={(citation) => {
        if (onCitationClick) {
          onCitationClick(
            visibleCitations,
            citation,
            message.diagnosticsTraceId
          );
        }
      }}
    />
    </div>
  ) : undefined;

  // In-flight turn: render the store-driven streaming body instead of the
  // committed chrome. Branches AFTER the hooks above so hook order is
  // stable across the streaming→committed transition.
  if (message?.isStreaming) {
    return (
      <MessagePrimitive.Root
        data-role="assistant"
        className="group relative mb-7 flex justify-start sm:mb-8"
      >
        <div className="min-w-0 flex-1 text-left">
          <AuiStreamingBody />
        </div>
      </MessagePrimitive.Root>
    );
  }

  // Recoverable failure (network error / empty response / stream exception):
  // render an error block with a prominent Retry button instead of an
  // ambiguous blank bubble. onRetry re-sends the prior user turn.
  if (message?.error) {
    const helperLine =
      ERROR_CATEGORY_HELP[message.error.category ?? ''] ?? message.content;
    const retryable = !NON_RETRYABLE_ERROR_CATEGORIES.has(
      message.error.category ?? ''
    );
    return (
      <MessagePrimitive.Root
        data-role="assistant"
        className="group relative mb-7 flex justify-start sm:mb-8"
      >
        <div className="min-w-0 flex-1 text-left">
          <div
            role="alert"
            className="inline-flex max-w-[92%] items-start gap-2 rounded-xl border border-(--nous-mars)/30 bg-(--nous-mars)/5 px-4 py-3 sm:max-w-[540px]"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-(--nous-mars)" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-(--nous-fg-1)">
                {message.error.message}
              </p>
              {helperLine ? (
                <p className="mt-1 text-[12px] text-(--nous-fg-3)">
                  {helperLine}
                </p>
              ) : null}
            </div>
          </div>
          {retryable ? (
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={onRetry}
                disabled={retryDisabled}
                title={retryDisabled ? RETRY_UNAVAILABLE_REASON : undefined}
                className="inline-flex items-center gap-1.5 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2) px-3 py-1.5 text-[12px] font-medium text-(--nous-fg-1) transition-colors hover:border-(--nous-sol)/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--nous-sol) disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          ) : null}
        </div>
      </MessagePrimitive.Root>
    );
  }

  return (
    <MessagePrimitive.Root
      data-role="assistant"
      className="group relative mb-7 flex justify-start sm:mb-8"
    >
      <div className="min-w-0 flex-1 text-left">
        {/* Execution plan — committed provenance for agent turns */}
        {message?.plan && message.plan.length > 0 && (
          <ChatInlinePlan
            plan={message.plan}
            reasoning={message.planReasoning}
            toolExecutions={message.toolExecutions}
            elapsedMs={message.metadata?.responseTimeMs}
            ttftMs={message.metadata?.ttftMs}
          />
        )}
        {/* Tool strip — tools/sources/time/tokens/stopped */}
        {message && (
          <ToolStrip {...getToolStripProps(message, visibleCitations.length)} />
        )}
        <MessageAttachments />
        <div className="nous-chat-body space-y-2">
          <MessageParts assistant assistantText={assistantText} />
        </div>
        <MessageError />
        {/* Citations footer chips — provenance over assertion */}
        {visibleCitations.length > 0 && (
          <CitationChips
            citations={visibleCitations}
            diagnosticsTraceId={message?.diagnosticsTraceId}
            onCitationClick={onCitationClick}
          />
        )}
        {/* Copy / regenerate / rate read as one row, but rating sits beside
         * the action bar rather than inside it: ActionBarPrimitive.Root
         * *unmounts* when the message is not hovered, which would discard a
         * half-typed feedback note and hide a rating the reader already gave.
         *
         * Rating renders first so the bar mounting on hover extends the row
         * to the right instead of shifting the thumbs under the pointer.
         * Persisted (server-canonical) turns only — optimistic rows have no
         * id to PATCH. */}
        <div className="nous-msg-actionrow">
          {message?.id ? (
            <MessageFeedback
              messageId={message.id}
              feedback={message.feedback}
            />
          ) : null}
          <MessageActions
            assistant
            onRetry={onRetry}
            retryDisabled={retryDisabled}
          />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
}

/**
 * Catches the transient out-of-bounds throw a single MessageByIndex can hit
 * when the external-store runtime's message array desyncs from the page list
 * on thread switch. The count guard in {@link AuiMessageByIndex} handles the
 * common post-commit lag, but under React's concurrent scheduler that guard
 * can read a stale (non-empty) count while MessageByIndex's own
 * useSyncExternalStore snapshot reads the freshly-emptied thread — a torn read
 * that throws "useClientLookup: Index N out of bounds" from inside the child's
 * store update, out of the render-time guard's reach (prod crash on thread
 * switch). That frame is transient: render nothing for it and re-attempt once
 * the runtime settles (resetKey changes). Anything else is a real bug —
 * rethrow it to the app's error boundary rather than silently swallow.
 */
export class MessageByIndexBoundary extends React.Component<
  { resetKey: string; children: ReactNode },
  { error: Error | null; lastResetKey: string }
> {
  constructor(props: { resetKey: string; children: ReactNode }) {
    super(props);
    this.state = { error: null, lastResetKey: props.resetKey };
  }

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }

  static getDerivedStateFromProps(
    props: { resetKey: string },
    state: { error: Error | null; lastResetKey: string }
  ): { error: Error | null; lastResetKey: string } | null {
    // Runtime settled (count / message identity changed) — drop the transient
    // error and re-attempt on the next render. Does not remount children.
    if (props.resetKey !== state.lastResetKey) {
      return { error: null, lastResetKey: props.resetKey };
    }
    return null;
  }

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      // Version-coupled: this matches @assistant-ui/react@0.14.29's transient
      // out-of-bounds message. If a version bump rewords it, the classifier
      // stops matching and the boundary rethrows (crash returns) — but the
      // "shrinks under a mounted message" test in AuiMessage.test.tsx drives
      // the REAL runtime OOB, so a wording change trips it red in CI. On a bump:
      // re-run that test and update this pattern if it fails.
      if (/out of bounds|useClientLookup/i.test(error.message)) return null;
      throw error;
    }
    return this.props.children;
  }
}

/** Per-row bindings for the runtime-rendered message components. The
 * components themselves are module-level (stable identity — see
 * {@link BOUND_MESSAGE_COMPONENTS}); the row's data reaches them through this
 * context instead of through closures baked into freshly-created functions. */
interface BoundMessageContextValue {
  message?: ChatPageMessage;
  onRetry?: () => void;
  retryDisabled?: boolean;
  onEdit?: (newContent: string) => void;
  editDisabled?: boolean;
  onCitationClick?: OnCitationClick;
}

const BoundMessageContext = createContext<BoundMessageContextValue>({});

function BoundUserMessage(): ReactElement {
  const { message, onEdit, editDisabled } = useContext(BoundMessageContext);
  return (
    <AuiUserMessage
      message={message}
      onEdit={message?.role === 'user' ? onEdit : undefined}
      editDisabled={editDisabled}
    />
  );
}

function BoundAssistantMessage(): ReactElement {
  const { message, onRetry, retryDisabled, onCitationClick } =
    useContext(BoundMessageContext);
  return (
    <AuiAssistantMessage
      message={message}
      onRetry={onRetry}
      retryDisabled={retryDisabled}
      onCitationClick={onCitationClick}
    />
  );
}

// Module-level and frozen: a components map rebuilt per render (or per
// message/handler change) hands React a NEW component type, which unmounts and
// remounts the whole message subtree — resetting action-bar state, re-parsing
// markdown, and discarding an in-progress inline edit draft.
const BOUND_MESSAGE_COMPONENTS = {
  UserMessage: BoundUserMessage,
  AssistantMessage: BoundAssistantMessage,
} as const;

export function AuiMessageByIndex({
  index,
  message,
  onRetry,
  retryDisabled,
  onEdit,
  editDisabled,
  onCitationClick,
}: {
  index: number;
  /** Source message for this index — threaded through so the assistant
   * renderer can show plan/strip/citations from the committed data. */
  message?: ChatPageMessage;
  onRetry?: () => void;
  /** True while a regenerate cannot be accepted (a turn is in flight). */
  retryDisabled?: boolean;
  /** Edit-and-resend handler for user messages at this index. */
  onEdit?: (newContent: string) => void;
  /** True while a resend cannot be accepted (a turn is in flight). */
  editDisabled?: boolean;
  onCitationClick?: OnCitationClick;
}): ReactElement | null {
  // The external-store runtime syncs in a useEffect (post-commit), so on
  // the render where the page's message list grows (thread load/switch,
  // first send) the runtime can still hold the previous — possibly empty —
  // thread. MessageByIndex throws on out-of-bounds, so skip the stale
  // frame; the effect fires immediately after commit and re-renders us.
  const runtimeMessageCount = useThread((t) => t.messages.length);

  // The components map is module-level (stable identity); only the row's DATA
  // changes, and it travels by context so a message refresh re-renders the
  // subtree instead of remounting it.
  const bindings = useMemo<BoundMessageContextValue>(
    () => ({
      message,
      onRetry,
      retryDisabled,
      onEdit,
      editDisabled,
      onCitationClick,
    }),
    [message, onRetry, retryDisabled, onEdit, editDisabled, onCitationClick]
  );

  if (index >= runtimeMessageCount) return null;

  // resetKey settles the boundary when the runtime re-syncs: count changes on
  // grow/shrink, and message id changes on thread switch even when counts match.
  return (
    <MessageByIndexBoundary
      resetKey={`${runtimeMessageCount}:${message?.runtimeId ?? index}`}
    >
      <BoundMessageContext.Provider value={bindings}>
        <ThreadPrimitive.MessageByIndex
          index={index}
          components={BOUND_MESSAGE_COMPONENTS}
        />
      </BoundMessageContext.Provider>
    </MessageByIndexBoundary>
  );
}

export function AuiMessages(): ReactElement {
  return (
    <ThreadPrimitive.Messages>
      {({ message }): ReactNode => {
        if (message.role === 'user') return <AuiUserMessage />;
        if (message.role === 'assistant') return <AuiAssistantMessage />;
        return null;
      }}
    </ThreadPrimitive.Messages>
  );
}
