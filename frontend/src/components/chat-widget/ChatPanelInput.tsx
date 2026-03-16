'use client';

/**
 * ChatPanelInput — Auto-resizing textarea (max 3 lines) + send button.
 * Enter sends, Shift+Enter adds a newline.
 */

import React, { useRef, useCallback, useEffect } from 'react';
import { Send } from 'lucide-react';

interface ChatPanelInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export function ChatPanelInput({
  value,
  onChange,
  onSend,
  disabled = false,
}: ChatPanelInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea up to 3 lines
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    // Approx 3 lines: line-height ~20px * 3 = 60px
    const maxHeight = 60;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) {
        onSend();
      }
    }
  };

  const handleSendClick = () => {
    if (value.trim() && !disabled) {
      onSend();
      textareaRef.current?.focus();
    }
  };

  return (
    <div className="px-3 py-2 border-t border-border">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your project..."
          disabled={disabled}
          rows={1}
          aria-label="Chat message input"
          className="flex-1 resize-none bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50 disabled:opacity-50 transition-colors"
        />
        <button
          onClick={handleSendClick}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="shrink-0 h-9 w-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
