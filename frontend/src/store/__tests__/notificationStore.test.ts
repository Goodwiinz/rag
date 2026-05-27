import { act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AppNotification } from '@/store/notificationStore';
import {
  selectByChannel,
  selectRecent,
  selectUnreadCount,
  useNotificationStore,
} from '@/store/notificationStore';

function notification(
  overrides: Partial<AppNotification> = {}
): AppNotification {
  return {
    id: 'notif-1',
    channel: 'system',
    title: 'System update',
    snippet: 'Background job finished',
    read: false,
    timestamp: new Date('2026-05-27T10:00:00.000Z'),
    severity: 'info',
    ...overrides,
  };
}

describe('useNotificationStore', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-27T10:04:00.000Z'));

    act(() => {
      useNotificationStore.getState().clearAll();
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('adds notifications as unread with generated ids and timestamps newest first', () => {
    act(() => {
      useNotificationStore.getState().addNotification({
        channel: 'document',
        title: 'Document indexed',
        snippet: 'paper.pdf is ready',
        severity: 'info',
        linkTo: '/documents',
      });
      useNotificationStore.getState().addNotification({
        channel: 'agent',
        title: 'Agent run completed',
        snippet: 'Summary generated',
        severity: 'info',
        linkTo: '/chat',
      });
    });

    const state = useNotificationStore.getState();

    expect(state.notifications).toHaveLength(2);
    expect(state.notifications[0]).toMatchObject({
      channel: 'agent',
      title: 'Agent run completed',
      snippet: 'Summary generated',
      read: false,
      severity: 'info',
      linkTo: '/chat',
    });
    expect(state.notifications[0].id).toMatch(/^notif-\d+-\d+$/);
    expect(state.notifications[0].timestamp).toEqual(
      new Date('2026-05-27T10:04:00.000Z')
    );
    expect(state.notifications[1].channel).toBe('document');
  });

  it('marks only the targeted notification as read and updates unread count', () => {
    act(() => {
      useNotificationStore.setState({
        notifications: [
          notification({ id: 'read-me', read: false }),
          notification({ id: 'leave-unread', read: false }),
        ],
      });
      useNotificationStore.getState().markRead('read-me');
    });

    const state = useNotificationStore.getState();

    expect(state.notifications).toEqual([
      expect.objectContaining({ id: 'read-me', read: true }),
      expect.objectContaining({ id: 'leave-unread', read: false }),
    ]);
    expect(selectUnreadCount(state)).toBe(1);
  });

  it('selects unread recent notifications by timestamp without including read items', () => {
    act(() => {
      useNotificationStore.setState({
        notifications: [
          notification({
            id: 'old-unread',
            timestamp: new Date('2026-05-27T09:00:00.000Z'),
          }),
          notification({
            id: 'new-read',
            read: true,
            timestamp: new Date('2026-05-27T11:00:00.000Z'),
          }),
          notification({
            id: 'new-unread',
            timestamp: new Date('2026-05-27T10:30:00.000Z'),
          }),
        ],
      });
    });

    const state = useNotificationStore.getState();

    expect(selectRecent(2)(state).map((n) => n.id)).toEqual([
      'new-unread',
      'old-unread',
    ]);
  });

  it('filters by channel and supports dismissing and clearing notifications', () => {
    act(() => {
      useNotificationStore.setState({
        notifications: [
          notification({ id: 'doc', channel: 'document' }),
          notification({ id: 'agent', channel: 'agent' }),
          notification({ id: 'system', channel: 'system' }),
        ],
      });
      useNotificationStore.getState().dismiss('agent');
    });

    let state = useNotificationStore.getState();
    expect(selectByChannel('document')(state).map((n) => n.id)).toEqual([
      'doc',
    ]);
    expect(state.notifications.map((n) => n.id)).toEqual(['doc', 'system']);

    act(() => {
      useNotificationStore.getState().clearAll();
    });

    state = useNotificationStore.getState();
    expect(state.notifications).toEqual([]);
    expect(selectUnreadCount(state)).toBe(0);
  });
});
