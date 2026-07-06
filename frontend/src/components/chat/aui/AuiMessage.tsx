'use client';

import React, { type ReactElement, type ReactNode } from 'react';
import {
  ActionBarPrimitive,
  ErrorPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from '@assistant-ui/react';
import { Copy, FileText, Image as ImageIcon, RotateCcw } from 'lucide-react';

import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { cn } from '@/lib/utils';

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

function MessageParts({ assistant }: { assistant?: boolean }) {
  return (
    <MessagePrimitive.Parts>
      {({ part }) => {
        switch (part.type) {
          case 'text':
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
  onRetry,
}: {
  onRetry?: () => void;
}): ReactElement {
  return (
    <MessagePrimitive.Root
      data-role="assistant"
      className="group relative mb-7 flex justify-start sm:mb-8"
    >
      <div className="min-w-0 text-left">
        <MessageAttachments />
        <div className="nous-chat-body space-y-2">
          <MessageParts assistant />
        </div>
        <MessageError />
        <MessageActions assistant onRetry={onRetry} />
      </div>
    </MessagePrimitive.Root>
  );
}

export function AuiMessageByIndex({
  index,
  onRetry,
}: {
  index: number;
  onRetry?: () => void;
}): ReactElement {
  return (
    <ThreadPrimitive.MessageByIndex
      index={index}
      components={{
        UserMessage: AuiUserMessage,
        AssistantMessage: () => <AuiAssistantMessage onRetry={onRetry} />,
      }}
    />
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
