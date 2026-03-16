'use client';

import React, { useRef, useEffect } from 'react';
import { Bot } from 'lucide-react';
import { AgentMessageItem } from './AgentMessageItem';
import type { AgentMessage } from '@/types/agent-chat';

interface AgentMessageListProps {
  messages: AgentMessage[];
  isStreaming: boolean;
}

export function AgentMessageList({
  messages,
  isStreaming,
}: AgentMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center mb-3">
          <Bot className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">AI Research Agent</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-[260px]">
          Ask questions, search papers, manage projects, and more. I can see
          your current page context.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.map((msg) => (
        <AgentMessageItem key={msg.id} message={msg} />
      ))}
      {isStreaming && messages[messages.length - 1]?.role !== 'assistant' && (
        <div className="flex gap-3 px-4 py-3 bg-muted/20">
          <div className="shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
            <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="flex items-center gap-1">
            <span
              className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce"
              style={{ animationDelay: '0ms' }}
            />
            <span
              className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce"
              style={{ animationDelay: '150ms' }}
            />
            <span
              className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce"
              style={{ animationDelay: '300ms' }}
            />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
