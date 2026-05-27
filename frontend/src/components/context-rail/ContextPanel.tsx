'use client';

import { Database, Globe } from 'lucide-react';
import { CollapsibleCard } from './CollapsibleCard';

interface ContextPanelProps {
  /** Whether workspace RAG is enabled for this thread. */
  ragEnabled?: boolean;
  /** Workspace name (shown as the RAG corpus label). */
  workspaceName?: string | null;
}

/**
 * Cowork-style "Context" card listing active connectors. Minimal for now —
 * shows RAG status and workspace name. Room to grow (web search, agent
 * tools) as they come online.
 */
export function ContextPanel({
  ragEnabled = false,
  workspaceName,
}: ContextPanelProps) {
  return (
    <CollapsibleCard title="Context">
      <div
        className="text-[11px] uppercase tracking-wider mb-2"
        style={{ color: 'var(--nous-fg-3)' }}
      >
        Connectors
      </div>
      <ul className="space-y-2" style={{ fontFamily: 'var(--nous-font-body)' }}>
        <li className="flex items-center gap-3 py-1">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded"
            style={{
              background: 'var(--nous-bg-1)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            <Database
              className="h-4 w-4"
              style={{
                color: ragEnabled ? 'var(--nous-sol)' : 'var(--nous-fg-3)',
              }}
            />
          </span>
          <div className="flex-1 min-w-0">
            <p
              className="text-[14px] truncate"
              style={{ color: 'var(--nous-fg-1)' }}
            >
              Workspace RAG
            </p>
            <p
              className="text-[12px] mt-0.5"
              style={{ color: 'var(--nous-fg-3)' }}
            >
              {ragEnabled
                ? workspaceName
                  ? `Active · ${workspaceName}`
                  : 'Active'
                : 'Off'}
            </p>
          </div>
        </li>
        <li
          className="flex items-center gap-3 py-1 opacity-60"
          title="Not yet connected"
        >
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded"
            style={{
              background: 'var(--nous-bg-1)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            <Globe
              className="h-4 w-4"
              style={{ color: 'var(--nous-fg-3)' }}
            />
          </span>
          <div className="flex-1 min-w-0">
            <p
              className="text-[14px] truncate"
              style={{ color: 'var(--nous-fg-1)' }}
            >
              Web search
            </p>
            <p
              className="text-[12px] mt-0.5"
              style={{ color: 'var(--nous-fg-3)' }}
            >
              Not connected
            </p>
          </div>
        </li>
      </ul>
    </CollapsibleCard>
  );
}
