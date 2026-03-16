'use client';

import React from 'react';
import { Bot, X } from 'lucide-react';
import { useAgentChatStore } from '@/store/agentChatStore';

export function AgentFAB() {
  const uiMode = useAgentChatStore((s) => s.uiMode);
  const toggle = useAgentChatStore((s) => s.toggle);
  const hasUnread = useAgentChatStore((s) => s.hasUnread);

  const isOpen = uiMode !== 'closed';

  return (
    <button
      onClick={toggle}
      aria-label={isOpen ? 'Close agent chat' : 'Open agent chat'}
      className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-all flex items-center justify-center group"
    >
      {isOpen ? <X className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
      {hasUnread && !isOpen && (
        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-destructive border-2 border-background" />
      )}
      {/* Keyboard shortcut hint */}
      {!isOpen && (
        <span className="absolute -top-8 right-0 text-[10px] text-muted-foreground bg-popover border border-border rounded px-1.5 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
          ⌘K
        </span>
      )}
    </button>
  );
}
