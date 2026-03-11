'use client';

/**
 * ChatPanel — Full chat panel assembling ChatContextBar, ChatMessageList,
 * and ChatPanelInput with header containing Quick Chat title, clear, and close buttons.
 */

import React, { useRef, useEffect } from 'react';
import { X, Trash2 } from 'lucide-react';
import { ChatContextBar } from './ChatContextBar';
import { ChatMessageList } from './ChatMessageList';
import { ChatPanelInput } from './ChatPanelInput';
import type {
  ContextChip,
  ContextChipKind,
  WidgetMessage,
} from '@/types/chat-widget';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ChatPanelProps {
  messages: WidgetMessage[];
  contextChips: ContextChip[];
  isStreaming: boolean;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onToggleChip: (kind: ContextChipKind) => void;
  onClear: () => void;
  onClose: () => void;
}

export function ChatPanel({
  messages,
  contextChips,
  isStreaming,
  inputValue,
  onInputChange,
  onSend,
  onToggleChip,
  onClear,
  onClose,
}: ChatPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Focus trap: keep Tab / Shift+Tab cycling within the panel
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    // Focus the first focusable element on mount
    const focusableElements =
      panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    if (focusableElements.length > 0) {
      focusableElements[0].focus();
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;

      const focusable =
        panel!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        // Shift+Tab: if focus is on first element, wrap to last
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        // Tab: if focus is on last element, wrap to first
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    panel.addEventListener('keydown', handleKeyDown);
    return () => panel.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div ref={panelRef} className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <h3 className="text-sm font-medium text-foreground">Quick Chat</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={onClear}
            aria-label="Clear chat messages"
            disabled={messages.length === 0}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onClose}
            aria-label="Close chat panel"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Context Bar */}
      <div className="shrink-0">
        <ChatContextBar chips={contextChips} onToggleChip={onToggleChip} />
      </div>

      {/* Message List */}
      <ChatMessageList messages={messages} isStreaming={isStreaming} />

      {/* Input */}
      <div className="shrink-0">
        <ChatPanelInput
          value={inputValue}
          onChange={onInputChange}
          onSend={onSend}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
