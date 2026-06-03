// src/store/notificationStore.ts
import { create } from 'zustand';
import type { NotificationChannel } from '@/components/notifications/types';

export interface AppNotification {
  id: string;
  channel: NotificationChannel;
  title: string;
  snippet: string;
  meta?: string;
  read: boolean;
  timestamp: Date;
  severity?: 'info' | 'warn' | 'error';
  linkTo?: string;
}

let counter = 0;
function genId() {
  return `notif-${Date.now()}-${++counter}`;
}

interface NotificationState {
  notifications: AppNotification[];

  addNotification: (
    n: Omit<AppNotification, 'id' | 'timestamp' | 'read'>
  ) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],

  addNotification: (n) =>
    set((s) => ({
      notifications: [
        { ...n, id: genId(), timestamp: new Date(), read: false },
        ...s.notifications,
      ],
    })),

  markRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),

  markAllRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, read: true })),
    })),

  dismiss: (id) =>
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
    })),

  clearAll: () => set({ notifications: [] }),
}));

// Selectors (use outside of store to avoid re-renders)
export const selectUnreadCount = (s: NotificationState) =>
  s.notifications.filter((n) => !n.read).length;

export const selectByChannel =
  (channel: NotificationChannel) => (s: NotificationState) =>
    s.notifications.filter((n) => n.channel === channel);

export const selectRecent = (count: number) => (s: NotificationState) =>
  s.notifications
    .filter((n) => !n.read)
    .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    .slice(0, count);
