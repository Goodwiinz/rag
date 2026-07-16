'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  Bell,
  ArrowRight,
  FileCheck2,
  Cpu,
  Activity,
  AtSign,
  ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from '@/components/ui/hover-card';
import {
  useNotificationStore,
  selectUnreadCount,
} from '@/store/notificationStore';
import type { NotificationChannel } from './types';

const channelColors: Record<NotificationChannel, string> = {
  document: 'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)]',
  agent: 'bg-indigo-500/10 text-indigo-500 dark:text-indigo-300',
  system: 'bg-amber-500/10 text-amber-500 dark:text-amber-300',
  collab: 'bg-emerald-400/10 text-emerald-600 dark:text-emerald-300',
  security: 'bg-red-500/10 text-red-500 dark:text-red-300',
};

function ChannelIcon({ channel }: { channel: NotificationChannel }) {
  switch (channel) {
    case 'document':
      return <FileCheck2 />;
    case 'agent':
      return <Cpu />;
    case 'system':
      return <Activity />;
    case 'collab':
      return <AtSign />;
    case 'security':
      return <ShieldAlert />;
  }
}

interface BellPopoverProps {
  active?: boolean;
}

export function BellPopover({ active }: BellPopoverProps) {
  const unreadCount = useNotificationStore(selectUnreadCount);
  const notifications = useNotificationStore((s) => s.notifications);
  const recent = React.useMemo(
    () =>
      notifications
        .filter((n) => !n.read)
        .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        .slice(0, 4),
    [notifications]
  );

  return (
    <HoverCard openDelay={200} closeDelay={150}>
      <HoverCardTrigger asChild>
        <Link
          href="/notifications"
          aria-label="Notifications"
          aria-current={active ? 'page' : undefined}
          data-tip="Notifications"
          className={cn(
            'rail-btn relative flex items-center justify-center w-9 h-9 rounded-lg transition-colors duration-150',
            active
              ? 'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)]'
              : 'text-[var(--nous-fg-3)] hover:bg-[var(--nous-aurum)] hover:text-[var(--nous-sol-safe)] dark:hover:bg-[var(--nous-ember)] dark:hover:text-[var(--nous-helios)]'
          )}
        >
          {active && (
            <span className="absolute -left-[10px] top-2 bottom-2 w-0.5 rounded-r bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]" />
          )}
          <Bell className="w-4 h-4 rail-icon" />
          {unreadCount > 0 && (
            <span className="absolute top-[3px] right-[2px] min-w-[14px] h-[14px] px-[3px] flex items-center justify-center rounded-full bg-[var(--nous-sol)] text-white text-[9px] font-bold font-[var(--nous-font-mono)] shadow-[0_0_0_2px_var(--nous-bg-2)] dark:shadow-[0_0_0_2px_var(--nous-nyx)]">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Link>
      </HoverCardTrigger>

      <HoverCardContent
        side="right"
        sideOffset={12}
        align="start"
        className={cn(
          'w-80 p-0 border-[var(--nous-border-1)]',
          'bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]',
          'shadow-[var(--nous-shadow-lg)]',
          'rounded-[var(--nous-radius-lg)]'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]">
          <span className="font-[family-name:var(--nous-font-heading)] text-sm font-semibold text-[var(--nous-fg-1)]">
            Notifications
          </span>
          {unreadCount > 0 && (
            <span className="font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.1em] uppercase text-[var(--nous-fg-3)]">
              {unreadCount} new
            </span>
          )}
        </div>

        {/* Items */}
        <div className="max-h-64 overflow-y-auto">
          {recent.length === 0 ? (
            <div className="py-8 text-center font-[family-name:var(--nous-font-body)] text-sm text-[var(--nous-fg-3)]">
              All caught up
            </div>
          ) : (
            recent.map((n) => (
              <Link
                key={n.id}
                href={n.linkTo || '/notifications'}
                className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--nous-aurum)]/30 dark:hover:bg-[var(--nous-ember)] transition-colors duration-100"
              >
                <span
                  className={cn(
                    'grid place-items-center shrink-0 h-7 w-7 rounded-md [&_svg]:h-3.5 [&_svg]:w-3.5',
                    channelColors[n.channel]
                  )}
                  data-notif-type={n.channel}
                >
                  <ChannelIcon channel={n.channel} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-[family-name:var(--nous-font-heading)] text-[13px] font-medium text-[var(--nous-fg-1)] truncate">
                    {n.title}
                  </div>
                  <div className="font-[family-name:var(--nous-font-body)] text-[12px] text-[var(--nous-fg-3)] truncate">
                    {n.snippet}
                  </div>
                </div>
                {!n.read && (
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--nous-sol)]" />
                )}
              </Link>
            ))
          )}
        </div>

        {/* Footer */}
        <Link
          href="/notifications"
          className="flex items-center justify-center gap-1.5 px-4 py-2.5 border-t border-[var(--nous-border-1)] dark:border-[var(--nous-shade)] font-[family-name:var(--nous-font-ui)] text-xs font-medium text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)] hover:bg-[var(--nous-aurum)]/20 dark:hover:bg-[var(--nous-ember)] transition-colors"
        >
          View all notifications
          <ArrowRight className="h-3 w-3" />
        </Link>
      </HoverCardContent>
    </HoverCard>
  );
}
