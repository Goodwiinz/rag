'use client';

import { Database, Globe, Activity } from 'lucide-react';
import { CollapsibleCard } from './CollapsibleCard';

interface ContextPanelProps {
  ragEnabled?: boolean;
  workspaceName?: string | null;
}

interface ConnectorRowProps {
  icon: React.ReactNode;
  name: string;
  status: 'active' | 'idle' | 'offline';
  detail?: string;
}

function ConnectorRow({ icon, name, status, detail }: ConnectorRowProps) {
  const isActive = status === 'active';
  const isOffline = status === 'offline';

  return (
    <li
      className={
        'group flex items-center gap-3 py-2 -mx-1 px-1 rounded transition-colors hover:bg-[var(--nous-aurum)]/30 dark:hover:bg-[var(--nous-ember)]/30 ' +
        (isOffline ? 'opacity-55' : '')
      }
    >
      <span
        className={
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors ' +
          (isActive
            ? 'bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] border border-[rgba(212,160,57,0.25)]'
            : 'bg-[var(--nous-bg-1)] dark:bg-[var(--nous-nyx)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]')
        }
      >
        <span
          className={
            'h-4 w-4 ' +
            (isActive
              ? 'text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)]'
              : 'text-[var(--nous-fg-3)]')
          }
        >
          {icon}
        </span>
      </span>

      <div className="flex-1 min-w-0">
        <p
          className="text-[13px] font-medium truncate text-[var(--nous-fg-1)]"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          {name}
        </p>
        <p
          className="text-[10px] mt-0.5 truncate text-[var(--nous-fg-3)]"
          style={{
            fontFamily: 'var(--nous-font-mono)',
            letterSpacing: '0.04em',
          }}
        >
          {detail ?? (isActive ? 'Active' : isOffline ? 'Offline' : 'Idle')}
        </p>
      </div>

      <span
        className={
          'w-1.5 h-1.5 rounded-full shrink-0 ' +
          (isActive
            ? 'bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]'
            : isOffline
              ? 'bg-[var(--nous-fg-3)]/40'
              : 'bg-[var(--nous-fg-3)]')
        }
        style={
          isActive
            ? {
                boxShadow: '0 0 0 2px rgba(212,160,57,0.18)',
                animation: 'nous-pulse 2s ease-in-out infinite',
              }
            : undefined
        }
        aria-label={status}
      />
    </li>
  );
}

export function ContextPanel({
  ragEnabled = false,
  workspaceName,
}: ContextPanelProps) {
  const activeCount = ragEnabled ? 1 : 0;
  const totalCount = 3;

  return (
    <CollapsibleCard
      title="Context"
      icon={<Activity className="h-3 w-3" strokeWidth={1.7} />}
      badge={`${activeCount}/${totalCount}`}
    >
      <div
        className="text-[9px] uppercase mb-2 mt-1 text-[var(--nous-fg-3)]"
        style={{
          fontFamily: 'var(--nous-font-mono)',
          letterSpacing: '0.18em',
        }}
      >
        Connectors
      </div>
      <ul className="space-y-0.5">
        <ConnectorRow
          icon={<Database className="h-4 w-4" strokeWidth={1.7} />}
          name="Workspace RAG"
          status={ragEnabled ? 'active' : 'idle'}
          detail={
            ragEnabled
              ? workspaceName
                ? `Active · ${workspaceName}`
                : 'Active'
              : 'Off'
          }
        />
        <ConnectorRow
          icon={<Globe className="h-4 w-4" strokeWidth={1.7} />}
          name="Web search"
          status="offline"
          detail="Not connected"
        />
        <ConnectorRow
          icon={<Activity className="h-4 w-4" strokeWidth={1.7} />}
          name="Agent tools"
          status="idle"
          detail="Ready"
        />
      </ul>
    </CollapsibleCard>
  );
}
