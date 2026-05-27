// src/components/notifications/NotificationList.tsx
'use client';

import * as React from 'react';
import { Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useNotificationStore } from '@/store/notificationStore';
import type { NotificationChannel } from './types';
import { ChannelTag } from './NotificationBadge';
import { NotificationCard } from './NotificationCard';

const CHANNELS: { key: NotificationChannel | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'document', label: 'Document' },
  { key: 'agent', label: 'Agent' },
  { key: 'system', label: 'System' },
  { key: 'collab', label: 'Collab' },
  { key: 'security', label: 'Security' },
];

export function NotificationList() {
  const [filter, setFilter] = React.useState<NotificationChannel | 'all'>(
    'all'
  );
  const notifications = useNotificationStore((s) => s.notifications);
  const markRead = useNotificationStore((s) => s.markRead);
  const markAllRead = useNotificationStore((s) => s.markAllRead);
  const dismiss = useNotificationStore((s) => s.dismiss);

  const filtered =
    filter === 'all'
      ? notifications
      : notifications.filter((n) => n.channel === filter);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-[family-name:var(--nous-font-heading)] text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]">
            Notifications
          </h1>
          <p className="mt-1 font-[family-name:var(--nous-font-body)] text-sm text-[var(--nous-fg-3)]">
            {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={markAllRead}
            className="font-[family-name:var(--nous-font-ui)] text-xs font-medium text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)] hover:underline underline-offset-2"
          >
            Mark all read
          </button>
        )}
      </div>

      {/* Channel filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        {CHANNELS.map((ch) => (
          <button
            key={ch.key}
            type="button"
            onClick={() => setFilter(ch.key)}
            className={cn(
              'inline-flex items-center gap-1.5',
              'px-2.5 py-[3px] rounded-full',
              'font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.12em] uppercase font-medium',
              'border transition-all duration-150',
              filter === ch.key
                ? 'bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] border-[rgba(212,160,57,0.28)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)] dark:border-[rgba(232,184,74,0.22)]'
                : 'bg-transparent text-[var(--nous-fg-3)] border-[var(--nous-border-1)] hover:text-[var(--nous-fg-1)] hover:border-[var(--nous-border-2)]'
            )}
          >
            {ch.label}
          </button>
        ))}
      </div>

      {/* Notification list */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="grid place-items-center h-12 w-12 rounded-full bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] mb-4">
            <Bell className="h-5 w-5 text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)]" />
          </div>
          <h3 className="font-[family-name:var(--nous-font-heading)] text-sm font-medium text-[var(--nous-fg-1)]">
            No notifications
          </h3>
          <p className="mt-1 font-[family-name:var(--nous-font-body)] text-sm text-[var(--nous-fg-3)]">
            {filter === 'all'
              ? "You're all caught up."
              : `No ${filter} notifications.`}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
            .map((n) => (
              <NotificationCard
                key={n.id}
                notification={n}
                onDismiss={dismiss}
                onRead={markRead}
              />
            ))}
        </div>
      )}
    </div>
  );
}
