'use client';

/**
 * ChatPanel — Placeholder panel for the floating chat widget.
 * Will be replaced with full implementation in Task 7.
 */

import React from 'react';
import { X } from 'lucide-react';

interface ChatPanelProps {
  onClose: () => void;
}

export function ChatPanel({ onClose }: ChatPanelProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Quick Chat</h3>
        <button
          onClick={onClose}
          aria-label="Close chat panel"
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Placeholder content */}
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-sm text-muted-foreground">Chat panel loading...</p>
      </div>
    </div>
  );
}
