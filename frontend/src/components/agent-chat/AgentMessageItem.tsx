'use client';

import React from 'react';
import { User, Bot } from 'lucide-react';
import { ToolExecutionCard } from './ToolExecutionCard';
import type { AgentMessage } from '@/types/agent-chat';

interface AgentMessageItemProps {
  message: AgentMessage;
}

export function AgentMessageItem({ message }: AgentMessageItemProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? '' : 'bg-muted/20'}`}>
      <div
        className={`shrink-0 h-6 w-6 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-primary/10 text-primary'
            : 'bg-muted text-muted-foreground'
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5" />
        ) : (
          <Bot className="h-3.5 w-3.5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-foreground whitespace-pre-wrap break-words">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" />
          )}
        </div>
        {/* Tool executions */}
        {message.toolExecutions?.map((exec) => (
          <ToolExecutionCard key={exec.id} execution={exec} />
        ))}
        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((cite, i) => (
              <span
                key={`${cite.documentId}-${i}`}
                className="inline-flex items-center text-[10px] bg-primary/10 text-primary rounded px-1.5 py-0.5"
                title={cite.snippet}
              >
                {cite.documentTitle}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
