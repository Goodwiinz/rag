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

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  isStreaming,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRafRef = useRef<number | null>(null);

  // rAF-throttled auto-scroll — avoids queueing multiple smooth-scroll
  // animations when messages arrive faster than a frame. Use 'auto'
  // (instant) during streaming to avoid catch-up jitter.
  useEffect(() => {
    if (scrollRafRef.current !== null) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      bottomRef.current?.scrollIntoView({
        behavior: isStreaming ? 'auto' : 'smooth',
      });
    });
  }, [messages, isStreaming]);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current !== null) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

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
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-pulse [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-pulse [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-pulse [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
});
