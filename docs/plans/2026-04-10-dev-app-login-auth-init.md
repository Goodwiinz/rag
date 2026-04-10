# Dev App Login Auth Init Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore a working client-side login flow by preventing Supabase browser client misconfiguration from breaking hydration and by surfacing actionable auth errors.

**Architecture:** Move Supabase browser client creation behind a validated lazy accessor so auth code does not execute at module import time. Update the auth store to obtain the client inside actions and initialization paths, then add focused tests for missing config and sign-in error behavior.

**Tech Stack:** Next.js, React, Zustand, Jest, Supabase SSR client

---

### Task 1: Lock In The Failure Mode

**Files:**
- Create: `frontend/src/lib/supabase/__tests__/client.test.ts`
- Modify: `frontend/src/setupTests.ts`

**Step 1: Write the failing test**

Add a test that resets `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`, then asserts the browser client accessor throws a descriptive build-time configuration error.

**Step 2: Run test to verify it fails**

Run: `npm test -- --runInBand src/lib/supabase/__tests__/client.test.ts`

Expected: FAIL because the current client module silently falls back and does not produce the intended error contract.

### Task 2: Lock In Store-Level Error Handling

**Files:**
- Modify: `frontend/src/store/__tests__/auth-store-login.test.ts`

**Step 1: Write the failing test**

Add a test that makes Supabase client creation fail and asserts `useAuthStore.getState().signIn(...)` rejects with a descriptive configuration error while leaving auth state unauthenticated.

**Step 2: Run test to verify it fails**

Run: `npm test -- --runInBand src/store/__tests__/auth-store-login.test.ts`

Expected: FAIL because the current store eagerly creates the client at module import time.

### Task 3: Implement Minimal Auth Client Fix

**Files:**
- Modify: `frontend/src/lib/supabase/client.ts`
- Modify: `frontend/src/stores/authStore.ts`

**Step 1: Write minimal implementation**

Replace eager module-scope client creation with a validated lazy accessor. Make store actions call the accessor inside `signIn`, `signUp`, `signOut`, `resetPassword`, `fetchProfile`, `initialize`, and auth state listeners so configuration failures are caught and reported instead of crashing hydration.

**Step 2: Run targeted tests**

Run:
- `npm test -- --runInBand src/lib/supabase/__tests__/client.test.ts`
- `npm test -- --runInBand src/store/__tests__/auth-store-login.test.ts`

Expected: PASS

### Task 4: Verify The Auth Slice

**Files:**
- Modify: `frontend/Dockerfile.prod` if a build-time guard is required

**Step 1: Add build-time guard only if needed**

If test evidence shows the only remaining failure mode is missing build args, add a minimal Docker build assertion so broken frontend images fail during CI instead of deploying.

**Step 2: Run verification**

Run:
- `npm test -- --runInBand src/lib/supabase/__tests__/client.test.ts src/store/__tests__/auth-store-login.test.ts src/store/__tests__/auth-store-signup.test.ts`
- `npm run type-check`

Expected: PASS
