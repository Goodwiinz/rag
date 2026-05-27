# NOUS Notifications System — Design

**Date:** 2026-05-26
**Status:** Approved
**Scope:** Frontend-only (Zustand store, no backend)

## Overview

Two UI surfaces: a bell hover preview (3-4 recent items) and a full `/notifications` inbox page with channel filtering. Notifications generated client-side from existing events, seeded with mocks for all 5 channels.

## Data Model

```ts
interface Notification {
  id: string;
  channel: NotificationChannel; // 'document' | 'agent' | 'system' | 'collab' | 'security'
  title: string;
  snippet: string;
  meta?: string;
  read: boolean;
  timestamp: Date;
  actions?: { label: string; href?: string }[];
  severity?: "info" | "warn" | "error";
  linkTo?: string;
}
```

## State Management

Flat Zustand store at `src/store/notificationStore.ts`. Matches existing project pattern (projectStore, etc.).

**Actions:** addNotification, markRead, markAllRead, dismiss, clearAll
**Derived:** unreadCount, getByChannel, getUnread, getRecent(n)

Store seeded with mock notifications across all 5 channels on creation.

## UI Surface 1: Bell Hover Preview

- Location: AppRail bell icon
- Trigger: hover shows popover with 3-4 most recent unread
- Badge: unread count replaces current dot indicator
- Footer: "View all" link to /notifications
- Click: navigates to /notifications (existing behavior)

## UI Surface 2: /notifications Page

- Route: `app/(dashboard)/notifications/page.tsx`
- Header: title + "Mark all read" button
- Filter row: channel pills (All | Document | Agent | System | Collab | Security)
- Notification cards use voice-per-channel mapping:
  - Document, Collab → Scholarly voice (serif, gold rail)
  - Agent → Mono voice (terminal, dark)
  - System → Outline alert style
  - Security → Block alert (filled, tinted)
- Empty state when no notifications match filter
- Each card: dismiss, mark-read on click, action buttons

## File Structure

```
src/store/notificationStore.ts
src/components/notifications/NotificationCard.tsx
src/components/notifications/NotificationList.tsx
src/components/notifications/BellPopover.tsx
app/(dashboard)/notifications/page.tsx
```

## Existing Components Used

NotificationBadge (CountBadge, ChannelTag, StatusPill), ScholarlyToast, MonoToast, BlockAlert, OutlineAlert — all from `src/components/notifications/`.

## Future Extension Points

- Wire real WebSocket events to `addNotification`
- Persist to localStorage for refresh survival
- Backend API when needed
