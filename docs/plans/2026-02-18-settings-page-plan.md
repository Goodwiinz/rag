# Settings Page Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the existing `/settings` UI with a light, screenshot-aligned settings panel containing My Account, Agent Usage, and Connected Apps sections.

**Architecture:** Keep implementation in the existing route component and render a centered split panel (left nav + right content) driven by local tab state. Reuse `useAuth()` for user email and static placeholder values for plan/usage data to avoid backend coupling in this pass.

**Tech Stack:** Next.js App Router, React client component state/hooks, TypeScript, Tailwind CSS, lucide-react icons

---

### Task 1: Replace legacy settings page shell and state model

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Write the failing test**

```ts
// Add or update a route-level UI test asserting these labels exist:
// "Settings", "My Account", "Agent Usage", "Connected Apps"
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- settings`
Expected: FAIL because current page uses terminal-themed sections and different labels.

**Step 3: Write minimal implementation**

```tsx
// Replace old section registry with tabs:
const sections = [
  { id: 'account', label: 'My Account' },
  { id: 'usage', label: 'Agent Usage' },
  { id: 'apps', label: 'Connected Apps' },
];
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- settings`
Expected: PASS for tab labels.

**Step 5: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): replace legacy shell with tabbed settings panel"
```

### Task 2: Implement My Account content block

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Write the failing test**

```ts
// Assert account tab renders:
// "Primary email", "Subscription", "View Plans", "Log out"
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- settings`
Expected: FAIL on missing account content.

**Step 3: Write minimal implementation**

```tsx
// Render account panel with user email from useAuth() and static subscription text
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- settings`
Expected: PASS for My Account fields/actions.

**Step 5: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): add my account section content"
```

### Task 3: Implement Agent Usage section with usage card and history table

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Write the failing test**

```ts
// Assert usage tab renders:
// "Plan", "Basic", "Monthly Credits", "History", "No usage history found"
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- settings`
Expected: FAIL on missing usage card/table.

**Step 3: Write minimal implementation**

```tsx
// Render plan/credits panel and simple history table shell with empty-state row
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- settings`
Expected: PASS for usage content.

**Step 5: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): add agent usage panel and history state"
```

### Task 4: Implement Connected Apps section and responsive polish

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Write the failing test**

```ts
// Assert connected apps tab renders connected apps title and empty-state helper text
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- settings`
Expected: FAIL on missing content.

**Step 3: Write minimal implementation**

```tsx
// Add connected apps state + empty list card and optional connect button placeholder
// Ensure mobile stacks sidebar/content
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- settings`
Expected: PASS for connected apps content.

**Step 5: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): add connected apps section and responsive layout"
```

### Task 5: Validate quality gates

**Files:**
- Modify (if required by fixes): `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Run focused checks**

Run: `cd frontend && npm run type-check && npm run lint`
Expected: PASS with no type/lint errors.

**Step 2: Run relevant tests**

Run: `cd frontend && npm run test -- settings`
Expected: PASS for settings-related tests.

**Step 3: Apply minimal fixes if needed**

```tsx
// Fix only failing assertions, accessibility attributes, or lint/type issues
```

**Step 4: Re-run checks**

Run: `cd frontend && npm run type-check && npm run lint && npm run test -- settings`
Expected: PASS.

**Step 5: Commit**

```bash
git add "frontend/app/(dashboard)/settings/page.tsx"
git commit -m "chore(settings): finalize validation for refreshed settings page"
```
