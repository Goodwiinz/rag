// src/components/notifications/NotificationList.tsx
'use client';

import * as React from 'react';
import { Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useNotificationStore } from '@/store/notificationStore';
import type { NotificationChannel } from './types';
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
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Notifications
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {unreadCount > 0 ? `${unreadCount} unread` : "You're all caught up"}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={markAllRead}
            className={cn(
              'rounded-md px-2 py-1 text-sm font-medium text-primary',
              'underline-offset-4 transition-colors hover:underline',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
            )}
          >
            Mark all read
          </button>
        )}
      </div>

      {/* Channel filter */}
      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Filter notifications by channel"
      >
        {CHANNELS.map((ch) => {
          const active = filter === ch.key;
          return (
            <button
              key={ch.key}
              type="button"
              onClick={() => setFilter(ch.key)}
              aria-pressed={active}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium',
                'transition-colors duration-150',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                active
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:border-border hover:text-foreground hover:bg-muted'
              )}
            >
              {ch.label}
            </button>
          );
        })}
      </div>

      {/* Notification list */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16 text-center shadow-sm">
          <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-primary/10">
            <Bell aria-hidden="true" className="h-5 w-5 text-primary" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">
            {filter === 'all'
              ? 'No notifications yet'
              : `No ${filter} notifications`}
          </h3>
          <p className="mt-1 max-w-xs text-sm text-muted-foreground">
            {filter === 'all'
              ? 'Updates about your documents, agents, and account will show up here.'
              : 'Try another channel, or switch back to all notifications.'}
          </p>
          {filter !== 'all' && (
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={cn(
                'mt-4 rounded-md px-2 py-1 text-sm font-medium text-primary',
                'underline-offset-4 transition-colors hover:underline',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'
              )}
            >
              Show all notifications
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered
            .slice()
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
