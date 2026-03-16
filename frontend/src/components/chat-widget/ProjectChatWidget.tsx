'use client';

/**
 * ProjectChatWidget — Root component rendering FAB + ChatPanel.
 * Fixed bottom-right floating action button that opens a chat panel.
 */

import React, { useEffect, useCallback } from 'react';
import { MessageSquare, X } from 'lucide-react';
import { ChatPanel } from './ChatPanel';
import { useProjectChatWidget } from '@/hooks/useProjectChatWidget';
import type { ChatWidgetTabType } from '@/types/chat-widget';

interface ProjectChatWidgetProps {
  projectId: string;
  activeTab: ChatWidgetTabType;
}

export function ProjectChatWidget({
  projectId,
  activeTab,
}: ProjectChatWidgetProps) {
  const widget = useProjectChatWidget({ projectId, activeTab });
  const { isOpen, close } = widget;

  // Escape key closes the panel
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        close();
      }
    },
    [isOpen, close]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* Mobile backdrop overlay — visible only on small screens when panel is open */}
      {widget.isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          aria-hidden="true"
          onClick={widget.close}
        />
      )}

      {/* Chat Panel */}
      {/* TODO: Add close animation (needs AnimatePresence or delayed unmount) */}
      {widget.isOpen && (
        <div
          className="fixed bottom-[88px] right-6 z-50 w-[380px] h-[520px] max-sm:w-full max-sm:h-[100dvh] max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:rounded-b-none max-sm:rounded-t-xl bg-background border border-border rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Project chat panel"
          aria-labelledby="chat-panel-title"
        >
          <ChatPanel
            messages={widget.messages}
            contextChips={widget.contextChips}
            isStreaming={widget.isStreaming}
            inputValue={widget.inputValue}
            onInputChange={widget.setInputValue}
            onSend={() => void widget.sendMessage()}
            onToggleChip={widget.toggleChip}
            onToggleAllChips={widget.toggleAllChips}
            onClear={widget.clearMessages}
            onClose={widget.close}
          />
        </div>
      )}

      {/* FAB */}
      <button
        onClick={widget.toggle}
        aria-label={widget.isOpen ? 'Close project chat' : 'Open project chat'}
        className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-all flex items-center justify-center"
      >
        {widget.isOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <MessageSquare className="h-5 w-5" />
        )}
        {widget.hasUnread && (
          <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-destructive border-2 border-background" />
        )}
      </button>
    </>
  );
}
