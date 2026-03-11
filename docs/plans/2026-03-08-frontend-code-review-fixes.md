# Frontend Code Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 14 findings from the comprehensive frontend code review, spanning security, accessibility, code quality, and reliability.

**Architecture:** Targeted fixes across existing files. No new architectural patterns — each task modifies 1-3 files with precise, testable changes. Tasks ordered by severity (critical first) and grouped by domain to minimize context-switching.

**Tech Stack:** Next.js 15, React 18, TypeScript, Zustand, DOMPurify (new dep for Task 3)

---

### Task 1: Fix WebSocket JWT in URL Query Params (Critical — Security)

**Files:**

- Modify: `frontend/src/services/realtimeWebSocketService.ts:126-129`

**Context:** The `realtimeWebSocketService.ts` passes the auth token as a URL query parameter (`wsUrl.searchParams.set('token', authToken)`). This exposes the token in browser history, server logs, and network proxies. The correct pattern already exists in `websocket-client.ts:139-145` — use `Sec-WebSocket-Protocol` header.

**Step 1: Write the failing test**

No test file exists for this service. Create `frontend/src/services/__tests__/realtimeWebSocketService.test.ts`:

```typescript
import { RealtimeWebSocketService } from "../realtimeWebSocketService";

// Mock WebSocket
const mockWebSocket = jest.fn();
(global as any).WebSocket = mockWebSocket;

describe("RealtimeWebSocketService", () => {
  beforeEach(() => {
    mockWebSocket.mockClear();
  });

  it("should NOT pass token as URL query parameter", () => {
    // When a connection is established, the URL should not contain the token
    const service = new RealtimeWebSocketService({
      url: "ws://localhost:8000/ws",
      connectionTimeout: 5000,
    });

    service.connect("test-token-123");

    // Get the URL that was passed to WebSocket constructor
    const calledUrl = mockWebSocket.mock.calls[0]?.[0];
    expect(calledUrl).not.toContain("token=");
    expect(calledUrl).not.toContain("test-token-123");
  });

  it("should pass token via Sec-WebSocket-Protocol", () => {
    const service = new RealtimeWebSocketService({
      url: "ws://localhost:8000/ws",
      connectionTimeout: 5000,
    });

    service.connect("test-token-123");

    // Second argument to WebSocket should be protocols array
    const protocols = mockWebSocket.mock.calls[0]?.[1];
    expect(protocols).toContain("auth");
    expect(protocols).toContain("test-token-123");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest src/services/__tests__/realtimeWebSocketService.test.ts --no-coverage`
Expected: FAIL (token is in URL, protocols not set)

**Step 3: Fix the implementation**

In `frontend/src/services/realtimeWebSocketService.ts`, replace lines 126-129:

```typescript
// BEFORE (insecure):
const wsUrl = new URL(this.config.url);
wsUrl.searchParams.set("token", authToken);
this.ws = new WebSocket(wsUrl.toString(), this.config.protocols);

// AFTER (secure):
const wsUrl = new URL(this.config.url);
// SECURITY: Use Sec-WebSocket-Protocol for token authentication (not URL params)
const protocols = ["auth", authToken];
this.ws = new WebSocket(wsUrl.toString(), protocols);
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/services/__tests__/realtimeWebSocketService.test.ts --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/services/realtimeWebSocketService.ts frontend/src/services/__tests__/realtimeWebSocketService.test.ts
git commit -m "fix(security): use Sec-WebSocket-Protocol instead of URL query param for auth token"
```

---

### Task 2: Add QueryClientProvider to App Providers (Critical — Runtime Crash)

**Files:**

- Modify: `frontend/app/providers.tsx`

**Context:** `providers.tsx` wraps the app in `AuthProvider` and `AuthSyncProvider`, but `QueryClientProvider` from TanStack Query is missing. Any page using `useQuery`/`useMutation` will crash with "No QueryClient set". The `QueryClient` must be created inside a `useState` to avoid re-creation on re-renders (Next.js App Router pattern).

**Step 1: Write the failing test**

Create `frontend/app/__tests__/providers.test.tsx`:

```typescript
import { render } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { Providers } from '../providers';

// Mock auth hooks to avoid Supabase initialization
jest.mock('@/hooks', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('@/components/auth/AuthSyncProvider', () => ({
  AuthSyncProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('react-hot-toast', () => ({
  Toaster: () => null,
}));

function TestQueryComponent() {
  const { data } = useQuery({
    queryKey: ['test'],
    queryFn: () => 'works',
    enabled: false,
  });
  return <div>query-mounted</div>;
}

describe('Providers', () => {
  it('provides QueryClient so useQuery does not throw', () => {
    // This will throw "No QueryClient set" if QueryClientProvider is missing
    expect(() =>
      render(
        <Providers>
          <TestQueryComponent />
        </Providers>
      )
    ).not.toThrow();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest app/__tests__/providers.test.tsx --no-coverage`
Expected: FAIL with "No QueryClient set"

**Step 3: Add QueryClientProvider**

Edit `frontend/app/providers.tsx`:

```typescript
'use client';

import { AuthSyncProvider } from '@/components/auth/AuthSyncProvider';
import { AuthProvider } from '@/hooks';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React, { useState } from 'react';
import { Toaster } from 'react-hot-toast';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
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

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthSyncProvider>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: 'hsl(var(--card))',
                color: 'hsl(var(--card-foreground))',
                border: '1px solid hsl(var(--border))',
              },
            }}
          />
        </AuthSyncProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default Providers;
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest app/__tests__/providers.test.tsx --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/providers.tsx frontend/app/__tests__/providers.test.tsx
git commit -m "fix: add QueryClientProvider to app providers to prevent runtime crashes"
```

---

### Task 3: Sanitize innerHTML in DraftViewer (Critical — XSS)

**Files:**

- Modify: `frontend/src/components/research/DraftViewer.tsx:241`
- Modify: `frontend/package.json` (add `dompurify` + `@types/dompurify`)

**Context:** `DraftViewer.tsx` renders LLM-generated markdown via innerHTML with `formatMarkdown(formattedContent)` (line 241). The comment says "internally-generated markdown only, not user input" but LLM output can contain injected HTML/scripts (prompt injection). The `formatMarkdown` function (lines 322-343) does regex-based markdown conversion but does NOT sanitize HTML tags. Fix: run the output through DOMPurify before rendering.

**Step 1: Install DOMPurify**

Run: `cd frontend && npm install dompurify && npm install -D @types/dompurify`

**Step 2: Sanitize the output**

In `frontend/src/components/research/DraftViewer.tsx`:

Add import at top:

```typescript
import DOMPurify from "dompurify";
```

Change the innerHTML usage on line 241. Replace `formatMarkdown(formattedContent)` with `DOMPurify.sanitize(formatMarkdown(formattedContent))`.

**Step 3: Run type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/research/DraftViewer.tsx frontend/package.json frontend/package-lock.json
git commit -m "fix(security): sanitize LLM-generated HTML with DOMPurify in DraftViewer"
```

---

### Task 4: Fix REACT*APP*\* Env Vars for Next.js (Important — Broken Config)

**Files:**

- Modify: `frontend/src/services/graphService.ts:70-72`
- Modify: `frontend/src/services/websocketService.ts:262,296`
- Modify: `frontend/src/services/analyticsService.ts:18`
- Modify: `frontend/src/services/graphAnalyticsService.ts:84`
- Modify: `frontend/src/services/evaluationService.ts:74,563`
- Modify: `frontend/src/hooks/useAnalytics.ts:117,133`
- Modify: `frontend/src/hooks/useEvaluation.ts:53`
- Modify: `frontend/src/hooks/useWebSocket.ts:36`

**Context:** Next.js only exposes env vars prefixed with `NEXT_PUBLIC_` to client-side code. All `process.env.REACT_APP_*` references resolve to `undefined` at runtime, so only the fallback values (`|| 'http://localhost:8000'`) are ever used. Replace all `REACT_APP_` with `NEXT_PUBLIC_` so these can be configured per environment.

**Step 1: Replace all occurrences**

For each file, do a find-and-replace of `REACT_APP_` with `NEXT_PUBLIC_`:

- `graphService.ts`:
  - `REACT_APP_GRAPH_SERVICE_URL` -> `NEXT_PUBLIC_GRAPH_SERVICE_URL`
  - `REACT_APP_GRAPH_ANALYTICS_URL` -> `NEXT_PUBLIC_GRAPH_ANALYTICS_URL`
  - `REACT_APP_GRAPH_VISUALIZATION_URL` -> `NEXT_PUBLIC_GRAPH_VISUALIZATION_URL`

- `websocketService.ts`:
  - `REACT_APP_GRAPH_WS_URL` -> `NEXT_PUBLIC_GRAPH_WS_URL`
  - `REACT_APP_ANALYTICS_WS_URL` -> `NEXT_PUBLIC_ANALYTICS_WS_URL`

- `analyticsService.ts`:
  - `REACT_APP_API_URL` -> `NEXT_PUBLIC_API_URL`

- `graphAnalyticsService.ts`:
  - `REACT_APP_GRAPH_ANALYTICS_URL` -> `NEXT_PUBLIC_GRAPH_ANALYTICS_URL`

- `evaluationService.ts`:
  - `REACT_APP_API_URL` -> `NEXT_PUBLIC_API_URL`
  - `REACT_APP_WS_URL` -> `NEXT_PUBLIC_WS_URL`

- `useAnalytics.ts`:
  - `REACT_APP_WS_URL` -> `NEXT_PUBLIC_WS_URL`

- `useEvaluation.ts`:
  - `REACT_APP_API_URL` -> `NEXT_PUBLIC_API_URL`

- `useWebSocket.ts`:
  - `REACT_APP_WS_URL` -> `NEXT_PUBLIC_WS_URL`

**Step 2: Run type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors (env vars are `string | undefined` either way)

**Step 3: Commit**

```bash
git add frontend/src/services/graphService.ts frontend/src/services/websocketService.ts frontend/src/services/analyticsService.ts frontend/src/services/graphAnalyticsService.ts frontend/src/services/evaluationService.ts frontend/src/hooks/useAnalytics.ts frontend/src/hooks/useEvaluation.ts frontend/src/hooks/useWebSocket.ts
git commit -m "fix: rename REACT_APP_* env vars to NEXT_PUBLIC_* for Next.js compatibility"
```

---

### Task 5: Fix useWebSocket Event Listener Cleanup (Important — Memory Leak)

**Files:**

- Modify: `frontend/src/hooks/useWebSocket.ts:28-107`

**Context:** The cleanup function calls `manager.off('connected')` without passing the handler function reference. This either removes ALL handlers for that event (breaking other subscribers) or does nothing (depending on the `off()` implementation). The handler functions (`handleConnected`, `handleDisconnected`, `handleError`) are defined inside the `connect` callback at lines 45-57, so we need to store them in refs to reference them during cleanup.

**Step 1: Fix the implementation**

In `frontend/src/hooks/useWebSocket.ts`:

1. Add refs for the handlers after line 28:

```typescript
const handlersRef = useRef<{
  connected: (() => void) | null;
  disconnected: (() => void) | null;
  error: ((data: any) => void) | null;
}>({ connected: null, disconnected: null, error: null });
```

2. Store handlers in refs after defining them (~line 57):

```typescript
handlersRef.current = {
  connected: handleConnected,
  disconnected: handleDisconnected,
  error: handleError,
};
```

3. Fix cleanup (lines 100-107):

```typescript
return () => {
  const manager = managerRef.current;
  const handlers = handlersRef.current;
  if (manager) {
    if (handlers.connected) manager.off("connected", handlers.connected);
    if (handlers.disconnected)
      manager.off("disconnected", handlers.disconnected);
    if (handlers.error) manager.off("error", handlers.error);
  }
};
```

**Step 2: Run type-check + tests**

Run: `cd frontend && npx tsc --noEmit && npx jest --no-coverage`
Expected: All pass

**Step 3: Commit**

```bash
git add frontend/src/hooks/useWebSocket.ts
git commit -m "fix: pass handler references to manager.off() for proper event listener cleanup"
```

---

### Task 6: Remove Debug Logging from Production Code (Important — Info Leak)

**Files:**

- Modify: `frontend/src/components/auth/AuthSyncProvider.tsx:12-29`
- Modify: `frontend/src/hooks/useChatPersistence.ts` (24 console.log calls)

**Context:**

- `AuthSyncProvider.tsx` has an unconditional `console.log` that dumps auth state (user ID, email, token presence) on every auth change. This leaks PII in production.
- `useChatPersistence.ts` has 24 `console.log` calls used for debugging. These should be gated behind `process.env.NODE_ENV === 'development'`.

**Step 1: Fix AuthSyncProvider**

In `frontend/src/components/auth/AuthSyncProvider.tsx`:

1. Remove the debug useEffect entirely (lines 20-29)
2. Remove unused destructured values — change line 13 from:
   `const { initializeFromStorage, isAuthenticated, user, token } = useAuthStore();`
   to:
   `const { initializeFromStorage } = useAuthStore();`
3. Remove unused `useEffect` import if no other effects remain (keep it — the first useEffect on line 15 still uses it)

**Step 2: Fix useChatPersistence**

In `frontend/src/hooks/useChatPersistence.ts`:

1. Add a `debugLog` helper at the top of the file (after imports):

```typescript
const debugLog =
  process.env.NODE_ENV === "development"
    ? (...args: unknown[]) => console.log(...args)
    : () => {};
```

2. Replace all `console.log('[useChatPersistence]` with `debugLog('[useChatPersistence]`. Keep `console.error` calls unchanged.

**Step 3: Run type-check + tests**

Run: `cd frontend && npx tsc --noEmit && npx jest --no-coverage`
Expected: All pass

**Step 4: Commit**

```bash
git add frontend/src/components/auth/AuthSyncProvider.tsx frontend/src/hooks/useChatPersistence.ts
git commit -m "fix: gate debug logging behind NODE_ENV check, remove PII leak in AuthSyncProvider"
```

---

### Task 7: Consolidate Duplicate useEffect in useAuth (Important — Redundancy)

**Files:**

- Modify: `frontend/src/hooks/useAuth.tsx:85-123`

**Context:** `useAuth.tsx` has two `useEffect` hooks that both sync auth state:

1. Lines 86-101: Sets local `authState` and syncs `setAuth`/`clearAuth`
2. Lines 108-123: Also syncs localStorage and calls `setAuth`/`clearAuth`

Both fire on `[token, user]` changes. The second effect duplicates the `setAuth`/`clearAuth` calls from the first. Merge them into one.

**Step 1: Merge the two useEffects**

Replace lines 85-123 with a single effect:

```typescript
// Sync auth state with store and localStorage
useEffect(() => {
  setAuthState({
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
  });

  // Keep the old API client and localStorage in sync
  try {
    if (token && user) {
      localStorage.setItem("access_token", token);
      localStorage.setItem("user_data", JSON.stringify(user));
      setAuth(token, user.organization_id);
    } else {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_data");
      clearAuth();
    }
  } catch (error) {
    console.error("Error syncing auth data to localStorage:", error);
  }
}, [user, token, isAuthenticated, isLoading, error, setAuth, clearAuth]);
```

**Step 2: Check if `storeAuthData` (lines 74-83) is used anywhere — if not, remove it**

**Step 3: Run type-check + tests**

Run: `cd frontend && npx tsc --noEmit && npx jest --no-coverage`
Expected: All pass

**Step 4: Commit**

```bash
git add frontend/src/hooks/useAuth.tsx
git commit -m "refactor: consolidate duplicate auth sync useEffects in useAuth"
```

---

### Task 8: Fix `as any` Casts in authStore (Important — Type Safety)

**Files:**

- Modify: `frontend/src/stores/authStore.ts:361-365,396`

**Context:** Two `set()` calls use `as any` to bypass TypeScript:

- Line 365: `set({ token, refreshTokenValue, tokenExpiresAt } as any)`
- Line 396: `set(updates as any)`

The `set` function from Zustand accepts `Partial<AuthState>`. Just remove the `as any` casts — the shapes are already compatible.

**Step 1: Fix the casts**

Line 365 — change:

```typescript
set({
  token: session.access_token,
  refreshTokenValue: session.refresh_token,
  tokenExpiresAt,
} as any);
```

to:

```typescript
set({
  token: session.access_token,
  refreshTokenValue: session.refresh_token ?? null,
  tokenExpiresAt,
});
```

Line 396 — change `set(updates as any);` to `set(updates);`

**Step 2: Run type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors. If errors appear, adjust the types accordingly.

**Step 3: Commit**

```bash
git add frontend/src/stores/authStore.ts
git commit -m "fix: remove 'as any' casts in authStore token refresh"
```

---

### Task 9: Fix Accessibility — aria-labels on Icon Buttons (Suggestion)

**Files:**

- Modify: `frontend/app/(dashboard)/chat/layout.tsx:695-699` (ContextPanel close button)
- Modify: `frontend/app/(auth)/login/page.tsx:390-394` (password toggle)

**Context:**

- ContextPanel close button uses `title="Close panel"` but should use `aria-label` for screen reader support.
- Login password toggle button has no accessible name at all.

**Step 1: Fix ContextPanel close button**

In `frontend/app/(dashboard)/chat/layout.tsx`, line 698:
Change `title="Close panel"` to `aria-label="Close context panel"`

**Step 2: Fix password toggle**

In `frontend/app/(auth)/login/page.tsx`, add aria-label to the password toggle button (line 390-393):

```typescript
<button
  type="button"
  onClick={() => setShowPassword(!showPassword)}
  className="..."
  aria-label={showPassword ? 'Hide password' : 'Show password'}
>
```

**Step 3: Run type-check + tests**

Run: `cd frontend && npx tsc --noEmit && npx jest --no-coverage`
Expected: All pass

**Step 4: Commit**

```bash
git add frontend/app/(dashboard)/chat/layout.tsx frontend/app/(auth)/login/page.tsx
git commit -m "fix(a11y): add aria-labels to icon-only buttons in ContextPanel and login form"
```

---

### Task 10: Wire Up CommandPalette Actions (Suggestion)

**Files:**

- Modify: `frontend/app/(dashboard)/chat/layout.tsx:38-138,200-241,1126-1129`

**Context:** The `CommandPalette` component renders commands (New Chat, Upload Document, Search, etc.) but both the Enter key handler (line 130) and button onClick (line 211) just call `onClose()` without executing the command. Add an `onExecute` callback prop.

**Step 1: Add onExecute prop to CommandPalette**

Modify the function signature (line 38):

```typescript
function CommandPalette({
  isOpen,
  onClose,
  onExecute,
}: {
  isOpen: boolean;
  onClose: () => void;
  onExecute?: (commandId: string) => void;
}) {
```

Modify Enter key handler (line 127-130):

```typescript
} else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
  e.preventDefault();
  onExecute?.(filteredCommands[selectedIndex].id);
  onClose();
}
```

Modify button onClick (line 211):

```typescript
onClick={() => {
  onExecute?.(cmd.id);
  onClose();
}}
```

**Step 2: Wire it up in ChatLayout (line 1126-1129)**

```typescript
<CommandPalette
  isOpen={commandPaletteOpen}
  onClose={() => setCommandPaletteOpen(false)}
  onExecute={(id) => {
    switch (id) {
      case 'new-chat':
        handleNewChat?.();
        break;
      case 'search':
        window.location.href = '/search';
        break;
      case 'arxiv':
        window.location.href = '/arxiv';
        break;
      case 'dashboard':
        window.location.href = '/dashboard';
        break;
      case 'entities':
        window.location.href = '/entities';
        break;
    }
  }}
/>
```

**Step 3: Run type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/app/(dashboard)/chat/layout.tsx
git commit -m "fix: wire up CommandPalette to execute commands on selection"
```

---

### Task 11: Add TTL to workspaceService Cache (Suggestion)

**Files:**

- Modify: `frontend/src/services/workspaceService.ts:436-497`

**Context:** `getOrCreateDefaultWorkspace()` caches the default workspace ID in localStorage with no expiration. Add a 24-hour TTL.

**Step 1: Add TTL logic**

Replace the cache check (lines 437-449):

```typescript
async getOrCreateDefaultWorkspace(): Promise<Workspace> {
  // Check localStorage cache first (24h TTL)
  if (typeof window !== 'undefined') {
    const cachedId = localStorage.getItem('default-workspace-id');
    const cachedAt = localStorage.getItem('default-workspace-cached-at');
    const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

    if (cachedId && cachedAt && Date.now() - Number(cachedAt) < TTL_MS) {
      try {
        const workspace = await this.getWorkspace(cachedId);
        return workspace;
      } catch (error: any) {
        if (error?.response?.status === 404) {
          localStorage.removeItem('default-workspace-id');
          localStorage.removeItem('default-workspace-cached-at');
        }
      }
    } else if (cachedId) {
      // TTL expired, clear stale cache
      localStorage.removeItem('default-workspace-id');
      localStorage.removeItem('default-workspace-cached-at');
    }
  }
```

Update both cache-set locations (~lines 467 and 496) to include timestamp:

```typescript
localStorage.setItem("default-workspace-id", bestWorkspace.id);
localStorage.setItem("default-workspace-cached-at", String(Date.now()));
```

**Step 2: Run type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/services/workspaceService.ts
git commit -m "fix: add 24h TTL to workspace ID cache in localStorage"
```

---

### Task 12: Fix layout.tsx Direct localStorage Read (Suggestion)

**Files:**

- Modify: `frontend/app/(dashboard)/chat/layout.tsx:598`

**Context:** `fetchSuggestions` reads `localStorage.getItem('access_token')` directly instead of using the auth store. Use `useAuthStore.getState().token` instead.

**Step 1: Fix the implementation**

Replace line 598:

```typescript
// BEFORE:
const token = localStorage.getItem("access_token");

// AFTER:
const token = useAuthStore.getState().token;
```

Add import at top if not already imported:

```typescript
import { useAuthStore } from "@/stores/authStore";
```

**Step 2: Run type-check + tests**

Run: `cd frontend && npx tsc --noEmit && npx jest --no-coverage`
Expected: All pass

**Step 3: Commit**

```bash
git add frontend/app/(dashboard)/chat/layout.tsx
git commit -m "fix: use auth store instead of direct localStorage read for access token"
```

---

## Summary

| Task | Severity   | Category    | Description                                           |
| ---- | ---------- | ----------- | ----------------------------------------------------- |
| 1    | Critical   | Security    | WebSocket JWT in URL params -> Sec-WebSocket-Protocol |
| 2    | Critical   | Runtime     | Add QueryClientProvider to app providers              |
| 3    | Critical   | Security    | Sanitize innerHTML with DOMPurify                     |
| 4    | Important  | Config      | Rename REACT*APP*_ to NEXT*PUBLIC*_                   |
| 5    | Important  | Memory      | Fix useWebSocket event listener cleanup               |
| 6    | Important  | Info Leak   | Gate debug console.log behind NODE_ENV                |
| 7    | Important  | Quality     | Consolidate duplicate useAuth effects                 |
| 8    | Important  | Types       | Remove `as any` casts in authStore                    |
| 9    | Suggestion | A11y        | Add aria-labels to icon buttons                       |
| 10   | Suggestion | UX          | Wire up CommandPalette to execute commands            |
| 11   | Suggestion | Reliability | Add TTL to workspace cache                            |
| 12   | Suggestion | Quality     | Replace direct localStorage read with auth store      |

**Estimated total: 12 tasks, 12 commits**
