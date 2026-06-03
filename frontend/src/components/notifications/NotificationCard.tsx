// src/components/notifications/NotificationCard.tsx
'use client';

import * as React from 'react';
import {
  FileCheck2,
  Cpu,
  Activity,
  AtSign,
  ShieldAlert,
  FileWarning,
  CircleCheck,
  Info,
  KeyRound,
  TriangleAlert,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AppNotification } from '@/store/notificationStore';
import type { NotificationChannel } from './types';

// Channel → icon mapping
const channelIcons: Record<NotificationChannel, React.ReactNode> = {
  document: <FileCheck2 />,
  agent: <Cpu />,
  system: <Activity />,
  collab: <AtSign />,
  security: <ShieldAlert />,
};

// Severity overrides for icons
function getIcon(n: AppNotification): React.ReactNode {
  if (n.channel === 'document' && n.severity === 'error')
    return <FileWarning />;
  if (n.channel === 'agent' && n.severity === 'info') return <CircleCheck />;
  if (n.channel === 'system' && n.severity === 'info') return <Info />;
  if (n.channel === 'system' && n.severity === 'warn') return <TriangleAlert />;
  if (n.channel === 'security')
    return n.severity === 'error' ? <ShieldAlert /> : <KeyRound />;
  return channelIcons[n.channel];
}

// Sentence-case channel labels
const channelLabels: Record<NotificationChannel, string> = {
  document: 'Document',
  agent: 'Agent',
  system: 'System',
  collab: 'Collab',
  security: 'Security',
};

// Severity is the only signal that earns a non-Sol color. We render it with
// the semantic destructive/foreground tokens AND a text label + icon, so color
// is never the sole status cue.
function severityLabel(severity?: AppNotification['severity']): string | null {
  if (severity === 'error') return 'Error';
  if (severity === 'warn') return 'Warning';
  return null;
}

interface NotificationCardProps {
  notification: AppNotification;
  onDismiss: (id: string) => void;
  onRead: (id: string) => void;
}

export function NotificationCard({
  notification: n,
  onDismiss,
  onRead,
}: NotificationCardProps) {
  const icon = getIcon(n);
  const isAlert = n.severity === 'error';
  const isWarn = n.severity === 'warn';
  const sev = severityLabel(n.severity);

  const handleClick = () => {
    if (!n.read) onRead(n.id);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  // One layout for every channel — earned familiarity. Channel is a quiet
  // label, severity is the only thing allowed to raise its voice (and only
  // for warn/error, via the semantic destructive token + a text label).
  return (
    <div
      role={isAlert ? 'alert' : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={n.read ? -1 : 0}
      className={cn(
        'group relative grid grid-cols-[auto_1fr_auto] items-start gap-3.5',
        'rounded-xl border bg-card px-4 py-3.5 shadow-sm',
        'transition-colors duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        n.read
          ? 'border-border opacity-70'
          : 'border-border hover:border-primary/40',
        isAlert && !n.read && 'border-destructive/40',
        !n.read && 'cursor-pointer'
      )}
    >
      {/* Icon tile — Sol accent by default, destructive only for warn/error */}
      <span
        aria-hidden="true"
        className={cn(
          'grid h-8 w-8 shrink-0 place-items-center rounded-lg',
          '[&_svg]:h-4 [&_svg]:w-4',
          isAlert || isWarn
            ? 'bg-destructive/10 text-destructive'
            : 'bg-primary/10 text-primary'
        )}
      >
        {icon}
      </span>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold tracking-[-0.005em] text-foreground">
            {n.title}
          </span>
          <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            {channelLabels[n.channel]}
          </span>
          {sev && (
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium',
                'bg-destructive/10 text-destructive'
              )}
            >
              {isAlert ? (
                <ShieldAlert aria-hidden="true" className="h-3 w-3" />
              ) : (
                <TriangleAlert aria-hidden="true" className="h-3 w-3" />
              )}
              {sev}
            </span>
          )}
          {!n.read && (
            <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-medium text-primary">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-primary"
              />
              Unread
            </span>
          )}
        </div>

        <p className="mt-1 font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
          {n.snippet}
        </p>

        {n.meta && (
          <p className="mt-1.5 text-xs text-muted-foreground/80">{n.meta}</p>
        )}
      </div>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(n.id);
        }}
        aria-label={`Dismiss notification: ${n.title}`}
        className={cn(
          'grid h-7 w-7 shrink-0 place-items-center rounded-md text-muted-foreground',
          'opacity-0 transition-all duration-200 group-hover:opacity-100 focus-visible:opacity-100',
          'hover:bg-muted hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
        )}
      >
        <X aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  );
}
