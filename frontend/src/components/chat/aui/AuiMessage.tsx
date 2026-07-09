'use client';

import React, { useMemo, type ReactElement, type ReactNode } from 'react';
import {
  ActionBarPrimitive,
  ErrorPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useThread,
} from '@assistant-ui/react';
import { Copy, FileText, Image as ImageIcon, RotateCcw } from 'lucide-react';

import { motion, useReducedMotion } from 'framer-motion';

import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { CitationRenderer } from '@/components/chat/CitationRenderer';
import { ChatInlinePlan } from '@/components/chat/shared/ChatInlinePlan';
import { CitationChips } from '@/components/chat/shared/CitationChips';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
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

function TextPart({ className }: { className?: string }) {
  return (
    <p className={cn('whitespace-pre-wrap text-[14px] leading-relaxed', className)}>
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

function ImagePart() {
  return (
    <MessagePartPrimitive.Image className="max-h-72 max-w-full rounded-xl border border-(--nous-border-1) object-contain" />
  );
}

function FilePart({ filename }: { filename?: string }) {
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
}) {
  return (
    <MessagePrimitive.Parts>
      {({ part }) => {
        switch (part.type) {
          case 'text':
            if (assistant && assistantText !== undefined) {
              return <>{assistantText}</>;
            }
            return <TextPart className={assistant ? 'font-serif' : undefined} />;
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

function AttachmentBadge({ type }: { type: string }) {
  if (type === 'image') {
    return <ImageIcon className="h-3.5 w-3.5 text-(--nous-fg-3)" />;
  }

  return (
    <span className="rounded bg-(--nous-aurum) px-1.5 py-0.5 text-[10px] font-semibold uppercase text-(--nous-sol-safe) dark:bg-(--nous-ember) dark:text-(--nous-helios)">
      {type === 'document' ? 'PDF' : 'File'}
    </span>
  );
}

function MessageAttachments() {
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

function MessageError() {
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
}: {
  assistant?: boolean;
  onRetry?: () => void;
}) {
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
        <Copy className="h-3.5 w-3.5" />
      </ActionBarPrimitive.Copy>
      {assistant && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="nous-msg-action"
          aria-label="Regenerate response"
          title="Regenerate response"
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

export function AuiUserMessage(): ReactElement {
  return (
    <MessagePrimitive.Root
      data-role="user"
      className="group relative mb-7 flex justify-end sm:mb-8"
    >
      <div className="min-w-0 text-right">
        <div className="nous-bubble-user relative inline-block max-w-[92%] px-4 py-2.5 text-left transition-shadow hover:shadow-md sm:max-w-[540px]">
          <MessageAttachments />
          <div className="nous-chat-body">
            <MessageParts />
          </div>
          <MessageError />
        </div>
        <MessageActions />
      </div>
    </MessagePrimitive.Root>
  );
}

/** Pre-first-token status pill (mirrors the legacy ChatBubble ThinkingPill). */
function StreamingThinkingPill({ label }: { label: string }): ReactElement {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="nous-streaming-pill"
      role="status"
      aria-live="polite"
      initial={reduce ? false : { opacity: 0, y: 2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
    >
      <span
        className="h-2 w-2 rounded-full bg-(--nous-sol) dark:bg-(--nous-helios)"
        style={{
          boxShadow: '0 0 0 3px rgba(var(--nous-sol-rgb), 0.18)',
          animation: 'nous-pulse 1.4s ease-in-out infinite',
        }}
      />
      <span>{label}</span>
    </motion.div>
  );
}

/**
 * Body of the in-flight assistant turn (AUI_FULL path). The message itself is
 * a stable placeholder in the transcript; its live text/steps/citations are
 * read from the streaming store here, so token updates re-render only this
 * component (a store-selector subscription) and never remount the message row.
 * Faithfully mirrors the render the legacy streaming ChatBubble produced.
 */
function AuiStreamingBody(): ReactElement {
  const content = useChatStore((s) => s.streamingContent);
  const steps = useChatStore((s) => s.streamingSteps);
  const isRetrievingRag = useChatStore((s) => s.isRetrievingRag);
  const streamingCitations = useChatStore((s) => s.streamingCitations);
  const threadId = useAgentActivityStore((s) => s.currentThreadId);
  const thinkingLabel = isRetrievingRag ? 'Reading sources' : 'Reflecting';

  return (
    <>
      <InlineAgentSummary threadId={threadId} />
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
        <StreamingThinkingPill label={thinkingLabel} />
      ) : (
        <div className="nous-chat-body">
          <CitationRenderer
            content={completeStreamingMarkdown(content)}
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

export function AuiAssistantMessage({
  message,
  onRetry,
  onCitationClick,
}: {
  /** Source ChatPageMessage for the committed turn. Drives the provenance
   * chrome the legacy ChatBubble rendered: plan, tool strip (incl. token
   * usage), markdown + inline citations, and citation footer chips. When
   * absent (e.g. plain AuiMessages usage), falls back to primitive text. */
  message?: ChatPageMessage;
  onRetry?: () => void;
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
    <CitationRenderer
      content={message.content}
      citations={allCitations}
      onCitationClick={(citation) => {
        if (onCitationClick) {
          onCitationClick(visibleCitations, citation, message.diagnosticsTraceId);
        }
      }}
    />
  ) : undefined;

  // In-flight turn (AUI_FULL): render the store-driven streaming body instead
  // of the committed chrome. Branches AFTER the hooks above so hook order is
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
            toolExecutions={message.toolExecutions}
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
        <MessageActions assistant onRetry={onRetry} />
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
      // Version-coupled: this matches @assistant-ui/react@0.14.26's transient
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

export function AuiMessageByIndex({
  index,
  message,
  onRetry,
  onCitationClick,
}: {
  index: number;
  /** Source message for this index — threaded through so the assistant
   * renderer can show plan/strip/citations from the committed data. */
  message?: ChatPageMessage;
  onRetry?: () => void;
  onCitationClick?: OnCitationClick;
}): ReactElement | null {
  // The external-store runtime syncs in a useEffect (post-commit), so on
  // the render where the page's message list grows (thread load/switch,
  // first send) the runtime can still hold the previous — possibly empty —
  // thread. MessageByIndex throws on out-of-bounds, so skip the stale
  // frame; the effect fires immediately after commit and re-renders us.
  const runtimeMessageCount = useThread((t) => t.messages.length);

  // Memoize the components map: a fresh AssistantMessage function identity
  // per render would make React treat it as a new component type and
  // unmount/remount the whole assistant subtree (resetting action-bar and
  // tool-card state, re-parsing markdown) instead of updating it.
  const components = useMemo(
    () => ({
      UserMessage: AuiUserMessage,
      AssistantMessage: function BoundAssistantMessage(): ReactElement {
        return (
          <AuiAssistantMessage
            message={message}
            onRetry={onRetry}
            onCitationClick={onCitationClick}
          />
        );
      },
    }),
    [message, onRetry, onCitationClick]
  );

  if (index >= runtimeMessageCount) return null;

  // resetKey settles the boundary when the runtime re-syncs: count changes on
  // grow/shrink, and message id changes on thread switch even when counts match.
  return (
    <MessageByIndexBoundary resetKey={`${runtimeMessageCount}:${message?.id ?? index}`}>
      <ThreadPrimitive.MessageByIndex index={index} components={components} />
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
