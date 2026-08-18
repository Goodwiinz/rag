'use client';

import React from 'react';
import { AlertCircle, MessageSquare } from 'lucide-react';
import type { AgentThread } from '@/types/agent-chat';

interface AgentThreadListProps {
  threads: AgentThread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  isLoading: boolean;
  /** Non-null when the list failed to load — rendering the empty state for a
   * failed request read as "you have no conversations". */
  error?: string | null;
  onRetry?: () => void;
}

export function AgentThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  isLoading,
  error = null,
  onRetry,
}: AgentThreadListProps) {
  if (isLoading) {
    return (
      <div className="p-3 space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded-md" />
        ))}
      </div>
    );
  }

  if (error && threads.length === 0) {
    return (
      <div
        role="alert"
        className="p-4 text-center text-xs text-muted-foreground space-y-2"
      >
        <AlertCircle aria-hidden className="h-4 w-4 mx-auto text-destructive" />
        <p>Could not load your conversations.</p>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="underline underline-offset-2 hover:text-foreground"
          >
            Try again
          </button>
        ) : null}
      </div>
    );
  }

  if (threads.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-muted-foreground">
        No conversations yet
      </div>
    );
  }

  return (
    <div className="p-2 space-y-1 overflow-y-auto">
      {threads.map((thread) => (
        <button
          key={thread.id}
          onClick={() => onSelectThread(thread.id)}
          className={`w-full text-left px-3 py-2 rounded-md text-xs transition-colors ${
            thread.id === activeThreadId
              ? 'bg-primary/10 text-primary'
              : 'text-foreground hover:bg-muted'
          }`}
        >
          <div className="flex items-center gap-2">
            <MessageSquare className="h-3 w-3 shrink-0" />
            <span className="truncate font-medium">{thread.title}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
            <span>{thread.messageCount} messages</span>
            <span>&middot;</span>
            <span>{formatRelativeDate(thread.updatedAt)}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function formatRelativeDate(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
