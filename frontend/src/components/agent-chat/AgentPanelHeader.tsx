'use client';

import React from 'react';
import { Maximize2, Trash2, X, Plus } from 'lucide-react';

interface AgentPanelHeaderProps {
  onExpand: () => void;
  onClear: () => void;
  onClose: () => void;
  onNewThread: () => void;
  hasMessages: boolean;
}

export function AgentPanelHeader({
  onExpand,
  onClear,
  onClose,
  onNewThread,
  hasMessages,
}: AgentPanelHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
      <h3
        id="agent-panel-title"
        className="text-sm font-medium text-foreground"
      >
        Agent
      </h3>
      <div className="flex items-center gap-1">
        <button
          onClick={onNewThread}
          aria-label="New conversation"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onClear}
          aria-label="Clear chat messages"
          disabled={!hasMessages}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onExpand}
          aria-label="Expand to sidebar"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onClose}
          aria-label="Close agent chat"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
