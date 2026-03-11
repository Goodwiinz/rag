'use client';

/**
 * ProjectChatWidget — Root component rendering FAB + ChatPanel.
 * Fixed bottom-right floating action button that opens a chat panel.
 */

import React, { useEffect, useCallback } from 'react';
import { MessageSquare } from 'lucide-react';
import { ChatPanel } from './ChatPanel';
import { useProjectChatWidget } from '@/hooks/useProjectChatWidget';

type TabType =
  | 'documents'
  | 'notes'
  | 'bibliography'
  | 'drafts'
  | 'chat'
  | 'matrix'
  | 'pipeline';

interface ProjectChatWidgetProps {
  projectId: string;
  activeTab: TabType;
}

export function ProjectChatWidget({
  projectId,
  activeTab,
}: ProjectChatWidgetProps) {
  const widget = useProjectChatWidget({ projectId, activeTab });

  // Escape key closes the panel
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && widget.isOpen) {
        widget.close();
      }
    },
    [widget]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* Chat Panel */}
      {widget.isOpen && (
        <div
          className="fixed bottom-20 right-6 z-50 w-[380px] h-[520px] max-sm:w-[calc(100vw-2rem)] max-sm:right-4 max-sm:bottom-20 bg-background border border-border rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
          role="dialog"
          aria-label="Project chat panel"
        >
          <ChatPanel onClose={widget.close} />
        </div>
      )}

      {/* FAB */}
      <button
        onClick={widget.toggle}
        aria-label={widget.isOpen ? 'Close chat' : 'Open chat'}
        className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-all flex items-center justify-center"
      >
        <MessageSquare className="h-5 w-5" />
        {widget.hasUnread && (
          <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-destructive border-2 border-background" />
        )}
      </button>
    </>
  );
}
