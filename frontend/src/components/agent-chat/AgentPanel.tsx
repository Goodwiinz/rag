'use client';

import React, { useRef, useEffect } from 'react';
import { AgentPanelHeader } from './AgentPanelHeader';
import { AgentContextBar } from './AgentContextBar';
import { AgentMessageList } from './AgentMessageList';
import { AgentInput } from './AgentInput';
import type { AgentMessage, PageContext } from '@/types/agent-chat';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface AgentPanelProps {
  messages: AgentMessage[];
  isStreaming: boolean;
  inputValue: string;
  pageContext: PageContext;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onClear: () => void;
  onClose: () => void;
  onExpand: () => void;
  onNewThread: () => void;
}

export function AgentPanel({
  messages,
  isStreaming,
  inputValue,
  pageContext,
  onInputChange,
  onSend,
  onClear,
  onClose,
  onExpand,
  onNewThread,
}: AgentPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Focus trap
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    requestAnimationFrame(() => {
      const textarea = panel.querySelector<HTMLElement>('textarea');
      textarea?.focus();
    });

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      const focusable =
        panel!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
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
      <AgentPanelHeader
        onExpand={onExpand}
        onClear={onClear}
        onClose={onClose}
        onNewThread={onNewThread}
        hasMessages={messages.length > 0}
      />
      <AgentContextBar context={pageContext} />
      <AgentMessageList messages={messages} isStreaming={isStreaming} />
      <AgentInput
        value={inputValue}
        onChange={onInputChange}
        onSend={onSend}
        disabled={isStreaming}
      />
    </div>
  );
}
