'use client';

/**
 * ChatMessageItem — Single message bubble.
 * User messages: right-aligned with primary background.
 * Assistant messages: left-aligned with muted background.
 */

import React from 'react';
import type { WidgetMessage } from '@/types/chat-widget';

interface ChatMessageItemProps {
  message: WidgetMessage;
}

export function ChatMessageItem({ message }: ChatMessageItemProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-sm'
            : 'bg-muted text-foreground rounded-bl-sm'
        }`}
      >
        {/* Content rendered as plain text via React escaping (XSS-safe).
            If markdown rendering is added, sanitize with DOMPurify. */}
        <p className="whitespace-pre-wrap break-words">{message.content}</p>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-foreground/10">
            <p className="text-[10px] uppercase tracking-wide opacity-60 mb-1">
              Sources
            </p>
            <div className="flex flex-wrap gap-1">
              {message.citations.map((citation, idx) => (
                <span
                  key={`${citation.documentId}-${idx}`}
                  className={`inline-block text-[10px] px-1.5 py-0.5 rounded ${
                    isUser
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : 'bg-background text-muted-foreground'
                  }`}
                  title={citation.snippet ?? citation.documentTitle}
                >
                  {citation.documentTitle}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Timestamp */}
        <p
          className={`text-[10px] mt-1 ${
            isUser ? 'text-primary-foreground/60' : 'text-muted-foreground/60'
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}
