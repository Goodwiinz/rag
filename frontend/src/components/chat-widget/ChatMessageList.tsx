'use client';

/**
 * ChatMessageList — Scrollable message list with auto-scroll,
 * empty state, and typing indicator.
 */

import React, { useRef, useEffect } from 'react';
import { MessageSquare } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessageItem } from './ChatMessageItem';
import type { WidgetMessage } from '@/types/chat-widget';

interface ChatMessageListProps {
  messages: WidgetMessage[];
  isStreaming: boolean;
}

export function ChatMessageList({
  messages,
  isStreaming,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or streaming starts
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  // Empty state
  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={MessageSquare}
          title="AWAITING_INPUT"
          description="Start a conversation to begin your research session."
        />
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div
        className="p-3"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg) => (
          <ChatMessageItem key={msg.id} message={msg} />
        ))}

        {/* Typing indicator */}
        {isStreaming && (
          <div className="flex justify-start mb-3">
            <div className="bg-muted rounded-lg rounded-bl-sm px-3 py-2">
              <div
                className="flex items-center gap-1"
                aria-label="Assistant is typing"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
