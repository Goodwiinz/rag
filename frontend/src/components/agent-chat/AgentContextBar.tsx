'use client';

import React from 'react';
import { MapPin } from 'lucide-react';
import type { PageContext } from '@/types/agent-chat';

interface AgentContextBarProps {
  context: PageContext;
}

export function AgentContextBar({ context }: AgentContextBarProps) {
  if (context.type === 'unknown') return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/30 text-xs text-muted-foreground">
      <MapPin className="h-3 w-3 shrink-0" />
      <span className="truncate">
        {context.type === 'project' && context.projectName
          ? `Project: ${context.projectName}`
          : context.label}
      </span>
    </div>
  );
}
