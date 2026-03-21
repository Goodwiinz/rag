'use client';

import React from 'react';
import { Maximize2, Trash2, X, Plus } from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';

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
        <IconButton
          icon={<Plus className="h-3.5 w-3.5" />}
          onClick={onNewThread}
          label="New conversation"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        />
        <IconButton
          icon={<Trash2 className="h-3.5 w-3.5" />}
          onClick={onClear}
          label="Clear chat messages"
          disabled={!hasMessages}
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        />
        <IconButton
          icon={<Maximize2 className="h-3.5 w-3.5" />}
          onClick={onExpand}
          label="Expand to sidebar"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        />
        <IconButton
          icon={<X className="h-4 w-4" />}
          onClick={onClose}
          label="Close agent chat"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        />
      </div>
    </div>
  );
}
