'use client';

import React, { useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';

interface AgentInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function AgentInput({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = 'Ask the agent...',
}: AgentInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && !isStreaming && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="border-t border-border p-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isStreaming}
          rows={1}
          className="flex-1 resize-none bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
        />
        {isStreaming && onStop ? (
          <button
            onClick={onStop}
            aria-label="Stop generation"
            className="shrink-0 h-9 w-9 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive flex items-center justify-center hover:bg-destructive/20 transition-colors"
          >
            <Square className="h-3.5 w-3.5" />
          </button>
        ) : (
          <button
            onClick={onSend}
            disabled={disabled || isStreaming || !value.trim()}
            aria-label="Send message"
            className="shrink-0 h-9 w-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
