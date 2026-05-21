# Frontend Performance Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical and high-priority performance issues identified in the frontend audit — dual QueryClient, WebSocket bugs, context re-renders, eager WASM loading, missing bundle optimizations, unnecessary client components, and unvirtualized lists.

**Architecture:** Targeted, independent fixes across providers, hooks, config, and components. No structural refactors — each task touches 1-3 files and produces a working, type-checked build. The chat page (1700 lines) and homepage (611 lines) splits are deferred to separate plans.

**Tech Stack:** Next.js 15, React 18, TanStack Query v5, Zustand, react-window, framer-motion

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/hooks/QueryProvider.tsx` | Delete | Remove unused dual QueryClient |
| `frontend/app/providers.tsx` | Modify | Consolidate QueryClient config |
| `frontend/src/hooks/useAnalytics.ts` | Modify | Fix WebSocket reconnection bug, disable duplicate polling |
| `frontend/src/components/realtime/RealtimeProcessingProvider.tsx` | Modify | Memoize context value |
| `frontend/src/providers/WebSocketProvider.tsx` | Modify | Memoize context value |
| `frontend/src/hooks/useWebLLM.ts` | Modify | Dynamic import @mlc-ai/web-llm |
| `frontend/next.config.js` | Modify | Add optimizePackageImports, splitChunks, compression |
| `frontend/app/(dashboard)/layout.tsx` | Modify | Split to server + client |
| `frontend/app/(dashboard)/dashboard-layout-client.tsx` | Create | Client wrapper for dashboard layout |
| `frontend/app/(dashboard)/documents/components/DocumentList.tsx` | Modify | Virtualize with react-window |

---

### Task 1: Consolidate QueryClient — remove unused dual instance

**Files:**
- Delete: `frontend/src/hooks/QueryProvider.tsx`
- Modify: `frontend/app/providers.tsx`

The app has two `QueryClient` instances: one in `src/hooks/QueryProvider.tsx` (module-level singleton, 5min staleTime, never imported) and one in `app/providers.tsx` (component-level, 1min staleTime, actually used). The `QueryProvider` component is exported but never imported anywhere — it's dead code. Remove it and consolidate the best settings into `providers.tsx`.

- [ ] **Step 1: Delete the unused QueryProvider**

Delete `frontend/src/hooks/QueryProvider.tsx` entirely.

```bash
rm frontend/src/hooks/QueryProvider.tsx
```

- [ ] **Step 2: Update providers.tsx with consolidated config**

In `frontend/app/providers.tsx`, update the `QueryClient` constructor (lines 17-26) to incorporate the better settings from the deleted file:

Replace:

```tsx
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  );
```

With:

```tsx
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000,
            gcTime: 10 * 60 * 1000,
            retry: 3,
            retryDelay: (attemptIndex) =>
              Math.min(1000 * 2 ** attemptIndex, 30000),
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 1,
            retryDelay: 1000,
          },
        },
      })
  );
```

- [ ] **Step 3: Check for any remaining imports of QueryProvider**

```bash
grep -rn "QueryProvider\|from.*QueryProvider" frontend/src/ frontend/app/ --include='*.tsx' --include='*.ts' | grep -v node_modules | grep -v '.test.'
```

Expected: no results (it was never imported). If any imports exist, update them to use `@tanstack/react-query` directly.

- [ ] **Step 4: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add -A frontend/src/hooks/QueryProvider.tsx frontend/app/providers.tsx
git commit -m "fix(perf): consolidate dual QueryClient into single instance"
```

---

### Task 2: Fix WebSocket reconnection bug and disable duplicate polling

**Files:**
- Modify: `frontend/src/hooks/useAnalytics.ts:102-158`

The `useRealTimeMetrics` hook has two bugs:
1. **Stale closure on reconnect** (line 148-150): `ws.onopen = newWs.onopen` assigns handlers to the closed `ws` instead of `newWs`
2. **Duplicate data source**: `useQuery` polls every 30s while a WebSocket pushes the same data. When the WebSocket is active, polling is wasteful.

- [ ] **Step 1: Rewrite useRealTimeMetrics**

In `frontend/src/hooks/useAnalytics.ts`, replace the entire `useRealTimeMetrics` function (lines 103-158) with:

```tsx
export const useRealTimeMetrics = () => {
  const queryClient = useQueryClient();
  const { setRealTimeMetrics, setRealTimeConnection } = useAnalyticsStore();
  const wsConnectedRef = React.useRef(false);

  const query = useQuery({
    queryKey: ['real-time-metrics'],
    queryFn: () => analyticsService.getRealTimeMetrics(),
    select: (data) => data.metrics,
    staleTime: 30 * 1000,
    gcTime: 2 * 60 * 1000,
    refetchInterval: () => (wsConnectedRef.current ? false : 30 * 1000),
  });

  React.useEffect(() => {
    if (query.data) {
      setRealTimeMetrics(query.data);
      setRealTimeConnection(true);
    }
    if (query.error) {
      setRealTimeConnection(false);
    }
  }, [query.data, query.error, setRealTimeMetrics, setRealTimeConnection]);

  React.useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connectWs = () => {
      ws = new WebSocket(`${getPublicWebSocketOrigin()}/analytics/metrics`);

      ws.onopen = () => {
        wsConnectedRef.current = true;
        setRealTimeConnection(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setRealTimeMetrics(data);
        queryClient.setQueryData(['real-time-metrics'], data);
      };

      ws.onclose = () => {
        wsConnectedRef.current = false;
        setRealTimeConnection(false);
        reconnectTimeout = setTimeout(connectWs, 5000);
      };
    };

    connectWs();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [queryClient, setRealTimeMetrics, setRealTimeConnection]);
};
```

Key changes:
- `refetchInterval` returns `false` when WebSocket is connected (disables polling)
- Reconnection creates a fresh `connectWs()` call instead of reassigning handlers on a closed socket
- Cleanup properly closes WebSocket and clears reconnect timeout

- [ ] **Step 2: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/hooks/useAnalytics.ts
git commit -m "fix(perf): fix WebSocket reconnection bug and disable redundant polling"
```

---

### Task 3: Memoize context provider values

**Files:**
- Modify: `frontend/src/components/realtime/RealtimeProcessingProvider.tsx:288-299`
- Modify: `frontend/src/providers/WebSocketProvider.tsx:46-50`

Both providers create new context value objects on every render, causing all consumers to re-render unnecessarily.

- [ ] **Step 1: Memoize RealtimeProcessingProvider context value**

In `frontend/src/components/realtime/RealtimeProcessingProvider.tsx`, add `useMemo` to the import on line 1:

Replace:

```tsx
import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useCallback,
} from 'react';
```

With:

```tsx
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useCallback,
} from 'react';
```

Then replace lines 294-299:

```tsx
  const contextValue: RealtimeProcessingContextType = {
    isConnected,
    reconnect,
    disconnect,
    manager: managerRef.current,
  };
```

With:

```tsx
  const contextValue = useMemo<RealtimeProcessingContextType>(
    () => ({
      isConnected,
      reconnect,
      disconnect,
      manager: managerRef.current,
    }),
    [isConnected, reconnect, disconnect]
  );
```

- [ ] **Step 2: Memoize WebSocketProvider context value**

In `frontend/src/providers/WebSocketProvider.tsx`, add `useMemo` to the import on line 1:

Replace:

```tsx
import React, { createContext, useContext, useEffect, ReactNode } from 'react';
```

With:

```tsx
import React, { createContext, useContext, useMemo, ReactNode } from 'react';
```

Then replace lines 46-50:

```tsx
  const contextValue: WebSocketContextType = {
    connection,
    sendMessage: connection.sendMessage,
    isReady,
  };
```

With:

```tsx
  const contextValue = useMemo<WebSocketContextType>(
    () => ({
      connection,
      sendMessage: connection.sendMessage,
      isReady,
    }),
    [connection, isReady]
  );
```

- [ ] **Step 3: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/realtime/RealtimeProcessingProvider.tsx frontend/src/providers/WebSocketProvider.tsx
git commit -m "fix(perf): memoize context provider values to prevent unnecessary re-renders"
```

---

### Task 4: Dynamic import @mlc-ai/web-llm

**Files:**
- Modify: `frontend/src/hooks/useWebLLM.ts:1`

The `@mlc-ai/web-llm` package includes a ~15MB WASM binary that's currently imported at the top level, inflating the initial bundle even when the user never uses local LLM inference.

- [ ] **Step 1: Convert to dynamic import**

In `frontend/src/hooks/useWebLLM.ts`, remove the static import on line 1:

```tsx
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
```

Replace with a type-only import and a dynamic loader:

```tsx
import type { InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
```

Then find the `loadModel` function in the hook (it calls `CreateMLCEngine`). Replace any usage of `CreateMLCEngine` with a dynamic import:

Find:

```tsx
      const newEngine = await CreateMLCEngine(modelId, {
```

Replace with:

```tsx
      const { CreateMLCEngine } = await import("@mlc-ai/web-llm");
      const newEngine = await CreateMLCEngine(modelId, {
```

- [ ] **Step 2: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/hooks/useWebLLM.ts
git commit -m "fix(perf): dynamic import web-llm to avoid 15MB WASM in initial bundle"
```

---

### Task 5: Merge optimization settings into next.config.js

**Files:**
- Modify: `frontend/next.config.js`

The active `next.config.js` is missing several optimizations present in the unused `next.optimized.config.js`: expanded `optimizePackageImports`, `modularizeImports`, and webpack `splitChunks`. We cherry-pick the safe, proven optimizations — not the full file (which has different env handling, Sentry-incompatible structure, and hardcoded localhost fallbacks).

- [ ] **Step 1: Expand optimizePackageImports**

In `frontend/next.config.js`, replace line 35:

```js
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
```

With:

```js
    optimizePackageImports: [
      'lucide-react',
      '@radix-ui/react-icons',
      'lodash-es',
      'date-fns',
      'recharts',
    ],
```

- [ ] **Step 2: Add modularizeImports**

In `frontend/next.config.js`, add after the `experimental` block (after line 36, before `images`):

```js
  // Tree-shaking for icon and utility libraries
  modularizeImports: {
    'lodash-es': {
      transform: 'lodash-es/{{member}}',
      preventFullImport: true,
    },
    'date-fns': {
      transform: 'date-fns/{{member}}',
      preventFullImport: true,
    },
  },
```

Note: Do NOT add lucide-react or @radix-ui here — `optimizePackageImports` already handles them in Next.js 15 and the two mechanisms conflict.

- [ ] **Step 3: Add webpack splitChunks**

In `frontend/next.config.js`, inside the `webpack` function (line 56), add splitChunks config at the top of the function body, before the `config.module.rules.push` call:

Replace:

```js
  webpack: (config, { isServer }) => {
    // Handle file uploads for documents
    config.module.rules.push({
```

With:

```js
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.optimization = {
        ...config.optimization,
        splitChunks: {
          ...config.optimization?.splitChunks,
          cacheGroups: {
            ...config.optimization?.splitChunks?.cacheGroups,
            vendor: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendors',
              chunks: 'all',
              priority: 10,
            },
            react: {
              test: /[\\/]node_modules[\\/](react|react-dom)[\\/]/,
              name: 'react',
              chunks: 'all',
              priority: 20,
            },
            ui: {
              test: /[\\/]node_modules[\\/](@radix-ui)[\\/]/,
              name: 'ui',
              chunks: 'all',
              priority: 15,
            },
          },
        },
      };
    }

    // Handle file uploads for documents
    config.module.rules.push({
```

- [ ] **Step 4: Verify build works**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/next.config.js
git commit -m "fix(perf): add tree-shaking, modularizeImports, and splitChunks to next.config"
```

---

### Task 6: Split dashboard layout into server + client

**Files:**
- Modify: `frontend/app/(dashboard)/layout.tsx`
- Create: `frontend/app/(dashboard)/dashboard-layout-client.tsx`

The dashboard layout is marked `'use client'` just for `usePathname()`, which forces ALL dashboard pages to hydrate as client components. Split into a server layout (default) that delegates to a thin client wrapper.

- [ ] **Step 1: Create the client wrapper**

Create `frontend/app/(dashboard)/dashboard-layout-client.tsx`:

```tsx
'use client';

import dynamic from 'next/dynamic';
import { SidebarLayout } from '@/components/layout/SidebarLayout';
import { usePathname } from 'next/navigation';

const GlobalAgentChat = dynamic(
  () =>
    import('@/components/agent-chat/GlobalAgentChat').then(
      (m) => m.GlobalAgentChat
    ),
  { ssr: false }
);

const NO_BREADCRUMB_PAGES = ['/'];
const NO_HEADER_PAGES = ['/chat'];

export default function DashboardLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const shouldShowBreadcrumb = !NO_BREADCRUMB_PAGES.includes(pathname || '');
  const shouldShowHeader = !NO_HEADER_PAGES.some(
    (page) => pathname === page || pathname?.startsWith(page + '/')
  );

  return (
    <SidebarLayout
      showBreadcrumb={shouldShowBreadcrumb}
      showHeader={shouldShowHeader}
      rightPanel={<GlobalAgentChat />}
    >
      {children}
    </SidebarLayout>
  );
}
```

- [ ] **Step 2: Convert the layout to a server component**

Replace the entire `frontend/app/(dashboard)/layout.tsx` with:

```tsx
import DashboardLayoutClient from './dashboard-layout-client';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
```

- [ ] **Step 3: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/app/\(dashboard\)/layout.tsx frontend/app/\(dashboard\)/dashboard-layout-client.tsx
git commit -m "fix(perf): split dashboard layout into server + client components"
```

---

### Task 7: Virtualize DocumentList

**Files:**
- Modify: `frontend/app/(dashboard)/documents/components/DocumentList.tsx`

The `DocumentList` component (321 lines) uses `.map()` to render all documents in the DOM. With 100+ documents this causes layout thrashing. The project already has `react-window` installed and uses `FixedSizeList` elsewhere.

- [ ] **Step 1: Add react-window import and refactor to virtualized rendering**

In `frontend/app/(dashboard)/documents/components/DocumentList.tsx`, add the import at the top:

```tsx
import { FixedSizeList as List } from 'react-window';
```

Then find the section where documents are mapped (the `<motion.div>` with `.map()` inside the document list container). Replace the `.map()` rendering with a virtualized list.

Find the pattern:

```tsx
{documents.map((doc, index) => (
  <motion.div
    key={doc.id}
```

Replace the entire `.map()` block with a `FixedSizeList`. The row renderer needs to receive the same props. Wrap the existing per-document JSX in a `Row` component:

Add before the `DocumentList` function:

```tsx
const ROW_HEIGHT = 72;
```

Inside the component, before the return statement, add:

```tsx
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const doc = documents[index];
    if (!doc) return null;
    return (
      <div style={style}>
```

Then wrap the existing per-document JSX inside this `Row` component (the `<motion.div key={doc.id} ...>` block), and replace the `.map()` with:

```tsx
<List
  height={Math.min(documents.length * ROW_HEIGHT, 600)}
  itemCount={documents.length}
  itemSize={ROW_HEIGHT}
  width="100%"
>
  {Row}
</List>
```

Note: The exact JSX varies — the engineer must read the current `.map()` block and wrap it. The key change is replacing `documents.map(...)` with `<List>{Row}</List>`. Remove the `motion.div` wrapper with stagger animations (`transition={{ delay: index * 0.03 }}`) — staggered animations on 100+ items are a performance anti-pattern.

- [ ] **Step 2: Verify and commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/app/\(dashboard\)/documents/components/DocumentList.tsx
git commit -m "fix(perf): virtualize DocumentList with react-window"
```

---

### Task 8: Type-check, test, and push

- [ ] **Step 1: Full type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 2: Run tests**

```bash
cd frontend && npx vitest run --passWithNoTests 2>&1 | tail -20
```

Expected: all existing tests pass.

- [ ] **Step 3: Push**

```bash
git push origin develop
```

---

## Out of Scope (separate plans)

These high-impact items require their own implementation plans:

- **Chat page refactor** (`app/(dashboard)/chat/page.tsx`, 1700 lines): Split into lazy-loaded sections (messages, sidebar, input), virtualize message list, memoize ChatMessage, wrap handleSubmit in useCallback
- **Homepage refactor** (`app/page.tsx`, 611 lines): Split into server component + client animation wrapper
- **Medium priority items**: Unused deps, syntax highlighter lazy-loading, graph lib deduplication, metadata exports, Zustand cache eviction, deprecated apiClient migration
