'use client';

import React, { useEffect, useCallback } from 'react';
import { AgentFAB } from './AgentFAB';
import { AgentPanel } from './AgentPanel';
import { AgentSidebar } from './AgentSidebar';
import { useAgentChatStore } from '@/store/agentChatStore';
import { usePageContext } from '@/hooks/usePageContext';

export function GlobalAgentChat() {
  const uiMode = useAgentChatStore((s) => s.uiMode);
  const messages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const inputValue = useAgentChatStore((s) => s.inputValue);
  const pageContext = useAgentChatStore((s) => s.pageContext);
  const close = useAgentChatStore((s) => s.close);
  const openSidebar = useAgentChatStore((s) => s.openSidebar);
  const setInputValue = useAgentChatStore((s) => s.setInputValue);
  const sendMessage = useAgentChatStore((s) => s.sendMessage);
  const clearMessages = useAgentChatStore((s) => s.clearMessages);
  const newThread = useAgentChatStore((s) => s.newThread);
  const setPageContext = useAgentChatStore((s) => s.setPageContext);

  // Auto-detect and update page context
  const detectedContext = usePageContext();
  useEffect(() => {
    setPageContext(detectedContext);
  }, [detectedContext, setPageContext]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to toggle
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        useAgentChatStore.getState().toggle();
      }
      // Escape to close
      if (e.key === 'Escape' && uiMode !== 'closed') {
        close();
      }
    },
    [uiMode, close]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* Mobile backdrop */}
      {uiMode !== 'closed' && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          aria-hidden="true"
          onClick={close}
        />
      )}

      {/* Panel mode */}
      {uiMode === 'panel' && (
        <div
          className="fixed bottom-[88px] right-6 z-50 w-[400px] h-[560px] max-sm:w-full max-sm:h-[100dvh] max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:rounded-b-none max-sm:rounded-t-xl bg-background border border-border rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Agent chat panel"
          aria-labelledby="agent-panel-title"
        >
          <AgentPanel
            messages={messages}
            isStreaming={isStreaming}
            inputValue={inputValue}
            pageContext={pageContext}
            onInputChange={setInputValue}
            onSend={() => void sendMessage()}
            onClear={clearMessages}
            onClose={close}
            onExpand={openSidebar}
            onNewThread={newThread}
          />
        </div>
      )}

      {/* Sidebar mode */}
      {uiMode === 'sidebar' && (
        <div
          className="fixed top-0 right-0 z-50 w-[420px] h-full bg-background border-l border-border shadow-xl animate-in slide-in-from-right duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Agent chat sidebar"
        >
          <AgentSidebar />
        </div>
      )}

      {/* FAB */}
      <AgentFAB />
    </>
  );
}
