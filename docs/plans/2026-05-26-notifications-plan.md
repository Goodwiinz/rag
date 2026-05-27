# NOUS Notifications — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a frontend notification system with bell hover preview and full inbox page, using existing NOUS notification components.

**Architecture:** Flat Zustand store seeded with mock data across 5 channels. Bell icon in AppRail gets a HoverCard showing recent unread. `/notifications` page renders filtered list with voice-per-channel card mapping.

**Tech Stack:** Zustand, Radix HoverCard, lucide-react, existing NOUS notification components, Next.js App Router.

---

### Task 1: Notification Store

**Files:**

- Create: `src/store/notificationStore.ts`

**Step 1: Create the Zustand store**

```ts
// src/store/notificationStore.ts
import { create } from "zustand";
import type { NotificationChannel } from "@/components/notifications/types";

export interface AppNotification {
  id: string;
  channel: NotificationChannel;
  title: string;
  snippet: string;
  meta?: string;
  read: boolean;
  timestamp: Date;
  severity?: "info" | "warn" | "error";
  linkTo?: string;
}

let counter = 0;
function genId() {
  return `notif-${Date.now()}-${++counter}`;
}

const MOCK_NOTIFICATIONS: AppNotification[] = [
  {
    id: genId(),
    channel: "document",
    title: "Indexing complete",
    snippet:
      "Heidegger — Being & Time.pdf embedded with bge-large · 482 chunks ready for retrieval.",
    meta: "2 min ago · workspace / Phenomenology",
    read: false,
    timestamp: new Date(Date.now() - 2 * 60_000),
    severity: "info",
    linkTo: "/documents",
  },
  {
    id: genId(),
    channel: "agent",
    title: "Agent paused — review required",
    snippet:
      "The literature-review agent flagged a citation it couldn't verify. Inspect step 7 to continue.",
    meta: "just now · run #c4a2",
    read: false,
    timestamp: new Date(Date.now() - 30_000),
    severity: "warn",
    linkTo: "/chat",
  },
  {
    id: genId(),
    channel: "system",
    title: "Model deprecation notice",
    snippet:
      "claude-3.5-sonnet will be retired on 2026-06-30. Migrating to claude-haiku-4-5 requires no code changes.",
    meta: "posted 12d ago · affects 4 of your agents",
    read: false,
    timestamp: new Date(Date.now() - 12 * 86_400_000),
    severity: "warn",
  },
  {
    id: genId(),
    channel: "collab",
    title: "Mira mentioned you",
    snippet:
      '"@you — does this graph match what you found in Sokal & Bricmont?"',
    meta: "5 min ago · thread / Postmodernism",
    read: false,
    timestamp: new Date(Date.now() - 5 * 60_000),
    linkTo: "/chat",
  },
  {
    id: genId(),
    channel: "security",
    title: "New sign-in detected",
    snippet: "A new sign-in from Berlin · Chrome on macOS.",
    meta: "14:08 UTC",
    read: false,
    timestamp: new Date(Date.now() - 3600_000),
    severity: "error",
  },
  {
    id: genId(),
    channel: "document",
    title: "3 documents failed to embed",
    snippet:
      "Husserl_Logical_Investigations.pdf — scanned, OCR confidence below threshold.",
    meta: "1 hour ago",
    read: true,
    timestamp: new Date(Date.now() - 3600_000),
    severity: "error",
    linkTo: "/documents",
  },
  {
    id: genId(),
    channel: "agent",
    title: "Run #c4a2 finished",
    snippet: "42 steps · 18.4s · $0.071",
    meta: "14:34:21 · AGT · run.complete",
    read: true,
    timestamp: new Date(Date.now() - 2 * 3600_000),
    severity: "info",
  },
  {
    id: genId(),
    channel: "system",
    title: "Approaching monthly quota",
    snippet: "You've used 84% of your 2M-token budget. Resets in 6 days.",
    meta: "today",
    read: true,
    timestamp: new Date(Date.now() - 4 * 3600_000),
    severity: "warn",
  },
];

interface NotificationState {
  notifications: AppNotification[];

  addNotification: (
    n: Omit<AppNotification, "id" | "timestamp" | "read">,
  ) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: MOCK_NOTIFICATIONS,

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
        n.id === id ? { ...n, read: true } : n,
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
```

**Step 2: Run type-check**

Run: `cd frontend && pnpm tsc --noEmit`
Expected: zero errors

**Step 3: Commit**

```bash
git add src/store/notificationStore.ts
git commit -m "feat(notifications): add Zustand notification store with mock data"
```

---

### Task 2: NotificationCard — Voice-Per-Channel Wrapper

**Files:**

- Create: `src/components/notifications/NotificationCard.tsx`

**Step 1: Build the unified card component**

This component picks the right visual voice based on notification channel:

- Document, Collab → Scholarly style (serif, gold rail)
- Agent → Mono style (terminal, dark)
- System → Outline alert style
- Security → Block alert (filled, tinted)

```tsx
// src/components/notifications/NotificationCard.tsx
"use client";

import * as React from "react";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AppNotification } from "@/store/notificationStore";
import type { NotificationChannel } from "./types";

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
  if (n.channel === "document" && n.severity === "error")
    return <FileWarning />;
  if (n.channel === "agent" && n.severity === "info") return <CircleCheck />;
  if (n.channel === "system" && n.severity === "info") return <Info />;
  if (n.channel === "system" && n.severity === "warn") return <TriangleAlert />;
  if (n.channel === "security")
    return n.severity === "error" ? <ShieldAlert /> : <KeyRound />;
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
        "cursor-pointer transition-opacity duration-150",
        n.read && "opacity-60",
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
  onDismiss: (id: string) => void,
) {
  switch (n.channel) {
    // Scholarly voice — serif, gold rail
    case "document":
    case "collab":
      return (
        <div
          className={cn(
            "relative grid grid-cols-[auto_1fr_auto] items-start",
            "gap-3.5 py-3.5 pl-[calc(18px+4px)] pr-[18px]",
            "bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)]",
            "rounded-[var(--nous-radius-lg)]",
            "shadow-[var(--nous-shadow-sm)]",
            "dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]",
            "group",
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
    case "agent":
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
              <span className="text-[var(--nous-dust)]">{n.title}:</span>{" "}
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
    case "system":
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
    case "security":
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
```

**Step 2: Type-check**

Run: `cd frontend && pnpm tsc --noEmit`

**Step 3: Commit**

```bash
git add src/components/notifications/NotificationCard.tsx
git commit -m "feat(notifications): add NotificationCard with voice-per-channel rendering"
```

---

### Task 3: NotificationList — Filtered List with Empty State

**Files:**

- Create: `src/components/notifications/NotificationList.tsx`

**Step 1: Build the list component**

```tsx
// src/components/notifications/NotificationList.tsx
"use client";

import * as React from "react";
import { Bell } from "lucide-react";
import { cn } from "@/lib/utils";
import { useNotificationStore } from "@/store/notificationStore";
import type { NotificationChannel } from "./types";
import { ChannelTag } from "./NotificationBadge";
import { NotificationCard } from "./NotificationCard";

const CHANNELS: { key: NotificationChannel | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "document", label: "Document" },
  { key: "agent", label: "Agent" },
  { key: "system", label: "System" },
  { key: "collab", label: "Collab" },
  { key: "security", label: "Security" },
];

export function NotificationList() {
  const [filter, setFilter] = React.useState<NotificationChannel | "all">(
    "all",
  );
  const notifications = useNotificationStore((s) => s.notifications);
  const markRead = useNotificationStore((s) => s.markRead);
  const markAllRead = useNotificationStore((s) => s.markAllRead);
  const dismiss = useNotificationStore((s) => s.dismiss);

  const filtered =
    filter === "all"
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
            {unreadCount > 0 ? `${unreadCount} unread` : "All caught up"}
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
              "inline-flex items-center gap-1.5",
              "px-2.5 py-[3px] rounded-full",
              "font-[family-name:var(--nous-font-mono)] text-[10px] tracking-[0.12em] uppercase font-medium",
              "border transition-all duration-150",
              filter === ch.key
                ? "bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] border-[rgba(212,160,57,0.28)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)] dark:border-[rgba(232,184,74,0.22)]"
                : "bg-transparent text-[var(--nous-fg-3)] border-[var(--nous-border-1)] hover:text-[var(--nous-fg-1)] hover:border-[var(--nous-border-2)]",
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
            {filter === "all"
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
```

**Step 2: Type-check**

Run: `cd frontend && pnpm tsc --noEmit`

**Step 3: Commit**

```bash
git add src/components/notifications/NotificationList.tsx
git commit -m "feat(notifications): add NotificationList with channel filters and empty state"
```

---

### Task 4: BellPopover — Hover Preview in AppRail

**Files:**

- Create: `src/components/notifications/BellPopover.tsx`
- Modify: `src/components/layout/AppRail.tsx`

**Step 1: Build the hover popover**

```tsx
// src/components/notifications/BellPopover.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { Bell, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/components/ui/hover-card";
import {
  useNotificationStore,
  selectUnreadCount,
  selectRecent,
} from "@/store/notificationStore";
import type { NotificationChannel } from "./types";

const channelColors: Record<NotificationChannel, string> = {
  document: "bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)]",
  agent: "bg-indigo-500/10 text-indigo-500 dark:text-indigo-300",
  system: "bg-amber-500/10 text-amber-500 dark:text-amber-300",
  collab: "bg-emerald-400/10 text-emerald-600 dark:text-emerald-300",
  security: "bg-red-500/10 text-red-500 dark:text-red-300",
};

interface BellPopoverProps {
  active?: boolean;
}

export function BellPopover({ active }: BellPopoverProps) {
  const unreadCount = useNotificationStore(selectUnreadCount);
  const recent = useNotificationStore(selectRecent(4));

  return (
    <HoverCard openDelay={200} closeDelay={150}>
      <HoverCardTrigger asChild>
        <Link
          href="/notifications"
          aria-label="Notifications"
          aria-current={active ? "page" : undefined}
          data-tip="Notifications"
          className={cn(
            "rail-btn relative flex items-center justify-center w-9 h-9 rounded-lg transition-colors duration-150",
            active
              ? "bg-[var(--nous-aurum)] text-[var(--nous-sol-safe)] dark:bg-[var(--nous-ember)] dark:text-[var(--nous-helios)]"
              : "text-[var(--nous-fg-3)] hover:bg-[var(--nous-aurum)] hover:text-[var(--nous-sol-safe)] dark:hover:bg-[var(--nous-ember)] dark:hover:text-[var(--nous-helios)]",
          )}
        >
          {active && (
            <span className="absolute -left-[10px] top-2 bottom-2 w-0.5 rounded-r bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]" />
          )}
          <Bell className="w-4 h-4 rail-icon" />
          {unreadCount > 0 && (
            <span className="absolute top-[3px] right-[2px] min-w-[14px] h-[14px] px-[3px] flex items-center justify-center rounded-full bg-[var(--nous-sol)] text-white text-[9px] font-bold font-[var(--nous-font-mono)] shadow-[0_0_0_2px_var(--nous-bg-2)] dark:shadow-[0_0_0_2px_var(--nous-nyx)]">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Link>
      </HoverCardTrigger>

      <HoverCardContent
        side="right"
        sideOffset={12}
        align="start"
        className={cn(
          "w-80 p-0 border-[var(--nous-border-1)]",
          "bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] dark:border-[var(--nous-shade)]",
          "shadow-[var(--nous-shadow-lg)]",
          "rounded-[var(--nous-radius-lg)]",
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
                href={n.linkTo || "/notifications"}
                className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--nous-aurum)]/30 dark:hover:bg-[var(--nous-ember)] transition-colors duration-100"
              >
                <span
                  className={cn(
                    "grid place-items-center shrink-0 h-7 w-7 rounded-md [&_svg]:h-3.5 [&_svg]:w-3.5",
                    channelColors[n.channel],
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

// Simple channel icon resolver
import { FileCheck2, Cpu, Activity, AtSign, ShieldAlert } from "lucide-react";

function ChannelIcon({ channel }: { channel: NotificationChannel }) {
  switch (channel) {
    case "document":
      return <FileCheck2 />;
    case "agent":
      return <Cpu />;
    case "system":
      return <Activity />;
    case "collab":
      return <AtSign />;
    case "security":
      return <ShieldAlert />;
  }
}
```

**Step 2: Update AppRail — replace Bell RailButton with BellPopover**

In `src/components/layout/AppRail.tsx`, replace the Bell `<RailButton>` with the new `<BellPopover>` component. Keep the same position in the nav order.

Replace:

```tsx
<RailButton
  icon={Bell}
  tip="Notifications"
  href="/notifications"
  active={isActive("/notifications")}
  dot
/>
```

With:

```tsx
<BellPopover active={isActive("/notifications")} />
```

Add import at top:

```tsx
import { BellPopover } from "@/components/notifications/BellPopover";
```

Remove `Bell` from the lucide-react import if no longer used elsewhere in the file.

**Step 3: Type-check**

Run: `cd frontend && pnpm tsc --noEmit`

**Step 4: Commit**

```bash
git add src/components/notifications/BellPopover.tsx src/components/layout/AppRail.tsx
git commit -m "feat(notifications): add bell hover popover with unread count badge"
```

---

### Task 5: Notifications Page

**Files:**

- Create: `app/(dashboard)/notifications/page.tsx`

**Step 1: Create the page**

```tsx
// app/(dashboard)/notifications/page.tsx
"use client";

import { NotificationList } from "@/components/notifications/NotificationList";

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <NotificationList />
    </div>
  );
}
```

**Step 2: Type-check**

Run: `cd frontend && pnpm tsc --noEmit`

**Step 3: Commit**

```bash
git add app/\(dashboard\)/notifications/page.tsx
git commit -m "feat(notifications): add /notifications inbox page"
```

---

### Task 6: Update barrel exports

**Files:**

- Modify: `src/components/notifications/index.ts`

**Step 1: Add new component exports**

Append to `src/components/notifications/index.ts`:

```ts
export { NotificationCard } from "./NotificationCard";
export { NotificationList } from "./NotificationList";
export { BellPopover } from "./BellPopover";
```

**Step 2: Type-check**

Run: `cd frontend && pnpm tsc --noEmit`

**Step 3: Commit**

```bash
git add src/components/notifications/index.ts
git commit -m "feat(notifications): export NotificationCard, NotificationList, BellPopover"
```

---

### Task 7: Visual verification

**Step 1: Start dev server**

Run: `cd frontend && pnpm dev`

**Step 2: Test in browser**

1. Open `http://localhost:3000/dashboard` — hover bell icon in sidebar, verify popover shows 4 unread notifications with count badge
2. Click bell → navigates to `/notifications`
3. On `/notifications` page: verify all 8 mock notifications render with correct voices (scholarly for document/collab, mono for agent, outline for system, block for security)
4. Click channel filter pills — verify filtering works
5. Click "Mark all read" — all items dim to 60% opacity, unread count clears
6. Dismiss individual notifications — verify they disappear
7. Toggle dark mode — verify all components render correctly
8. Check empty state — dismiss all, verify empty illustration appears

**Step 3: Final commit if any fixes needed**
