'use client';

import React, { useMemo, type ReactElement, type ReactNode } from 'react';
import {
  ActionBarPrimitive,
  ErrorPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from '@assistant-ui/react';
import { Copy, FileText, Image as ImageIcon, RotateCcw } from 'lucide-react';

import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { CitationRenderer } from '@/components/chat/CitationRenderer';
import { ChatInlinePlan } from '@/components/chat/shared/ChatInlinePlan';
import { CitationChips } from '@/components/chat/shared/CitationChips';
import {
  ToolStrip,
  getToolStripProps,
} from '@/components/chat/shared/ToolStrip';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { cn } from '@/lib/utils';
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
}): ReactElement {
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

  return <ThreadPrimitive.MessageByIndex index={index} components={components} />;
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
