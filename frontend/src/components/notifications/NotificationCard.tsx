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

  const handleClick = () => {
    if (!n.read) onRead(n.id);
  };

  // Base wrapper — all voices share this outer container
  // The voice-specific rendering is inside
  return (
    <div
      onClick={handleClick}
      className={cn(
        'cursor-pointer transition-opacity duration-150',
        n.read && 'opacity-60'
      )}
      data-notif-type={n.channel}
    >
      {renderByVoice(n, icon, onDismiss)}
    </div>
  );
}

function renderByVoice(
  n: AppNotification,
  icon: React.ReactNode,
  onDismiss: (id: string) => void
) {
  switch (n.channel) {
    // Scholarly voice — serif, gold rail
    case 'document':
    case 'collab':
      return (
        <div
          className={cn(
            'relative grid grid-cols-[auto_1fr_auto] items-start',
            'gap-3.5 py-3.5 pl-[calc(18px+4px)] pr-[18px]',
            'bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]',
            'rounded-[var(--nous-radius-lg)]',
            'shadow-[var(--nous-shadow-sm)]',
            'dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
            'group'
          )}
        >
          <span className="absolute left-0 top-3.5 bottom-3.5 w-[3px] rounded-r-sm bg-[var(--type-marker,var(--nous-sol))]" />
          <span className="grid place-items-center h-[30px] w-[30px] shrink-0 rounded-[var(--nous-radius-md)] bg-[var(--type-bg)] text-[var(--type-fg)] border border-[var(--type-border)] [&_svg]:h-3.5 [&_svg]:w-3.5">
            {icon}
          </span>
          <div className="min-w-0">
            <span className="font-[family-name:var(--nous-font-heading)] text-[13.5px] font-semibold tracking-[-0.005em] text-[var(--nous-fg-1)]">
              {n.title}
            </span>
            <div className="mt-0.5 font-[family-name:var(--nous-font-body)] text-sm leading-[1.5] text-[var(--nous-fg-2)]">
              {n.snippet}
            </div>
            {n.meta && (
              <div className="mt-1.5 font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
                {n.meta}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss(n.id);
            }}
            aria-label="Dismiss"
            className="opacity-0 group-hover:opacity-100 grid place-items-center h-5 w-5 rounded text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-all duration-150"
          >
            ×
          </button>
        </div>
      );

    // Mono voice — terminal
    case 'agent':
      return (
        <div className="relative grid grid-cols-[auto_1fr_auto] items-start gap-3.5 py-3.5 px-[18px] bg-[var(--nous-erebus)] text-[var(--nous-ivory)] border border-white/[0.06] rounded-[var(--nous-radius-md)] shadow-[var(--nous-shadow-sm)] overflow-hidden">
          <span className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--type-marker,var(--nous-sol))] to-transparent opacity-60" />
          <span className="grid place-items-center h-[26px] w-[26px] shrink-0 rounded-[var(--nous-radius-sm)] bg-white/[0.04] text-[var(--type-marker,var(--nous-helios))] border border-[var(--type-border)] [&_svg]:h-[13px] [&_svg]:w-[13px]">
            {icon}
          </span>
          <div className="min-w-0 font-[family-name:var(--nous-font-mono)]">
            {n.meta && (
              <div className="mb-1 text-[9.5px] uppercase tracking-[0.14em] text-[var(--nous-dust)]">
                {n.meta}
              </div>
            )}
            <div className="text-[12.5px] leading-[1.5]">
              <span className="text-[var(--nous-dust)]">{n.title}:</span>{' '}
              <span className="text-[var(--nous-helios)]">{n.snippet}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss(n.id);
            }}
            aria-label="Dismiss"
            className="text-[var(--nous-dust)] hover:text-[var(--nous-ivory)] text-xs transition-colors"
          >
            ×
          </button>
        </div>
      );

    // Outline — informational
    case 'system':
      return (
        <div className="grid grid-cols-[4px_1fr_auto] bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)] rounded-[var(--nous-radius-md)] overflow-hidden dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)] group">
          <span className="w-1 self-stretch rounded-[2px] bg-[var(--type-marker)]" />
          <div className="min-w-0 py-3 px-3.5">
            <div className="mb-1 flex items-center gap-2">
              <span className="shrink-0 text-[var(--type-marker)] [&_svg]:h-3.5 [&_svg]:w-3.5">
                {icon}
              </span>
              <span className="font-[family-name:var(--nous-font-heading)] text-[13.5px] font-semibold text-[var(--nous-fg-1)]">
                {n.title}
              </span>
            </div>
            <div className="font-[family-name:var(--nous-font-body)] text-[13.5px] leading-[1.55] text-[var(--nous-fg-2)]">
              {n.snippet}
            </div>
            {n.meta && (
              <div className="mt-1.5 font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
                {n.meta}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss(n.id);
            }}
            aria-label="Dismiss"
            className="self-start mt-3 mr-3 opacity-0 group-hover:opacity-100 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] text-xs transition-all"
          >
            ×
          </button>
        </div>
      );

    // Block — demands attention
    case 'security':
      return (
        <div className="grid grid-cols-[auto_1fr_auto] items-start gap-3.5 py-3.5 px-4 bg-[var(--type-bg)] border border-[var(--type-border)] rounded-[var(--nous-radius-md)] group">
          <span className="grid place-items-center shrink-0 text-[var(--type-fg)] [&_svg]:h-6 [&_svg]:w-6">
            {icon}
          </span>
          <div className="min-w-0">
            <span className="font-[family-name:var(--nous-font-heading)] text-[14px] font-semibold tracking-[-0.005em] text-[var(--nous-fg-1)]">
              {n.title}
            </span>
            <div className="mt-1 font-[family-name:var(--nous-font-body)] text-[13.5px] leading-[1.55] text-[var(--nous-fg-2)]">
              {n.snippet}
            </div>
            {n.meta && (
              <div className="mt-1.5 font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.05em] text-[var(--nous-fg-3)]">
                {n.meta}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss(n.id);
            }}
            aria-label="Dismiss"
            className="opacity-0 group-hover:opacity-100 text-[var(--type-fg)] hover:text-[var(--nous-fg-1)] text-xs transition-all"
          >
            ×
          </button>
        </div>
      );
  }
}
