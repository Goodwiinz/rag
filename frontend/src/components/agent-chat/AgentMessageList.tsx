'use client';

import React, { useRef, useEffect } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { AgentMessageItem } from './AgentMessageItem';
import { ConfirmationCard } from './ConfirmationCard';
import { useAgentChatStore } from '@/store/agentChatStore';
import type { AgentMessage } from '@/types/agent-chat';

interface AgentMessageListProps {
  messages: AgentMessage[];
  isStreaming: boolean;
}

export function AgentMessageList({
  messages,
  isStreaming,
}: AgentMessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pendingConfirmation = useAgentChatStore((s) => s.pendingConfirmation);
  const confirmAction = useAgentChatStore((s) => s.confirmAction);
  const retryLastMessage = useAgentChatStore((s) => s.retryLastMessage);

  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages.length, isStreaming, pendingConfirmation]);

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

  // Determine thinking indicator content
  const lastMessage = messages[messages.length - 1];
  const runningTool = lastMessage?.toolExecutions?.find(
    (te) => te.status === 'running'
  );
  const showThinkingIndicator =
    isStreaming && lastMessage?.role === 'assistant' && !lastMessage?.content;

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto">
      {messages.map((msg) => (
        <AgentMessageItem
          key={msg.id}
          message={msg}
          onRetry={msg.isError ? retryLastMessage : undefined}
        />
      ))}

      {/* Thinking / tool running indicator */}
      {showThinkingIndicator && (
        <div className="flex gap-3 px-4 py-3 bg-muted/20">
          <div className="shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
            <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          {runningTool ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Running: {runningTool.toolDisplayName}...</span>
            </div>
          ) : (
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
          )}
        </div>
      )}

      {/* Confirmation card */}
      {pendingConfirmation && (
        <div className="px-4 py-2">
          <ConfirmationCard
            tools={pendingConfirmation.tools}
            message={pendingConfirmation.message}
            onConfirm={() => void confirmAction(true)}
            onCancel={() => void confirmAction(false)}
          />
        </div>
      )}
    </div>
  );
}
