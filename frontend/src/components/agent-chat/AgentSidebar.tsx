'use client';

import React, { useEffect } from 'react';
import { Minimize2, Plus, X } from 'lucide-react';
import { AgentContextBar } from './AgentContextBar';
import { AgentMessageList } from './AgentMessageList';
import { AgentInput } from './AgentInput';
import { AgentThreadList } from './AgentThreadList';
import { useAgentChatStore } from '@/store/agentChatStore';

export function AgentSidebar() {
  const messages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const inputValue = useAgentChatStore((s) => s.inputValue);
  const pageContext = useAgentChatStore((s) => s.pageContext);
  const threads = useAgentChatStore((s) => s.threads);
  const activeThreadId = useAgentChatStore((s) => s.activeThreadId);
  const isLoadingThreads = useAgentChatStore((s) => s.isLoadingThreads);
  const close = useAgentChatStore((s) => s.close);
  const openPanel = useAgentChatStore((s) => s.openPanel);
  const setInputValue = useAgentChatStore((s) => s.setInputValue);
  const sendMessage = useAgentChatStore((s) => s.sendMessage);
  const newThread = useAgentChatStore((s) => s.newThread);
  const selectThread = useAgentChatStore((s) => s.selectThread);
  const loadThreads = useAgentChatStore((s) => s.loadThreads);
  const loadThreadMessages = useAgentChatStore((s) => s.loadThreadMessages);

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  const handleSelectThread = (threadId: string) => {
    selectThread(threadId);
    void loadThreadMessages(threadId);
  };

  return (
    <div className="flex h-full">
      {/* Thread list sidebar */}
      <div className="w-[200px] border-r border-border flex flex-col shrink-0">
        <div className="flex items-center justify-between px-3 py-3 border-b border-border">
          <span className="text-xs font-medium text-foreground">Threads</span>
          <button
            onClick={newThread}
            aria-label="New conversation"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        <AgentThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <h3
            id="agent-panel-title"
            className="text-sm font-medium text-foreground"
          >
            Agent
          </h3>
          <div className="flex items-center gap-1">
            <button
              onClick={openPanel}
              aria-label="Collapse to panel"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Minimize2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={close}
              aria-label="Close agent chat"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <AgentContextBar context={pageContext} />
        <AgentMessageList messages={messages} isStreaming={isStreaming} />
        <AgentInput
          value={inputValue}
          onChange={setInputValue}
          onSend={() => void sendMessage()}
          disabled={isStreaming}
        />
      </div>
    </div>
  );
}
