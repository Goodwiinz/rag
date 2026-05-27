# Settings Overview Hub Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the sparse `/settings` panel with a NOUS-branded SaaS-style settings overview hub and add valid App Router destinations for organization and API key settings.

**Architecture:** Keep `/settings` as the overview hub inside the existing dashboard shell, driven by lightweight local data plus `useAuth()` for user identity. Add two App Router subroutes for `/settings/organization` and `/settings/api-keys`, and use shared card-based styling so the settings suite feels cohesive without inventing backend persistence in this pass.

**Tech Stack:** Next.js 15 App Router, React 18 client components, TypeScript, Tailwind CSS, lucide-react, existing shadcn/ui primitives, Jest + Testing Library

**Execution skills:** `@test-driven-development`, `@vercel-react-best-practices`, `@verification-before-completion`

---

### Task 1: Reframe the settings route contract in tests

**Files:**
- Modify: `frontend/src/components/layout/__tests__/SettingsPage.test.tsx`

**Step 1: Write the failing test**

```tsx
it('renders the settings overview hub with summary cards', () => {
  render(<SettingsPage />);

  expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  expect(screen.getByText(/manage your account, workspace governance/i)).toBeInTheDocument();
  expect(screen.getByText('Workspace')).toBeInTheDocument();
  expect(screen.getByText('Role')).toBeInTheDocument();
  expect(screen.getByText('Plan')).toBeInTheDocument();
  expect(screen.getByText('Security')).toBeInTheDocument();
  expect(screen.getByText('API Access')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /open workspace & access/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /open developer access/i })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: FAIL because the current page still renders the older modal-style account/usage/apps tabs.

**Step 3: Add additional failing expectations for removed modal affordances**

```tsx
expect(screen.queryByRole('button', { name: 'Close settings' })).not.toBeInTheDocument();
expect(screen.queryByTestId('settings-panel')).not.toBeInTheDocument();
```

**Step 4: Run test to verify it still fails for the right reasons**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: FAIL on missing overview content and presence of the old modal shell.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/__tests__/SettingsPage.test.tsx
git commit -m "test(settings): redefine overview hub expectations"
```

### Task 2: Replace `/settings` with the NOUS overview hub

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Write the minimal page data model inline**

```tsx
const overviewStats = [
  { label: 'Workspace', value: 'Default Research Workspace', hint: 'Active tenant context' },
  { label: 'Role', value: 'Admin', hint: 'Full governance access' },
  { label: 'Plan', value: 'Research Pro', hint: '428 credits remain this cycle' },
  { label: 'Security', value: 'Protected', hint: 'Audit + encryption active' },
  { label: 'API Access', value: '2 tokens', hint: 'OpenAI and Anthropic ready' },
];
```

**Step 2: Implement the page header and status strip**

```tsx
<header className="space-y-3">
  <p className="text-xs font-mono uppercase tracking-[0.28em] text-[var(--phosphor-green)]">
    SYSTEM_SETTINGS
  </p>
  <div className="space-y-2">
    <h1 className="text-3xl font-semibold text-[var(--terminal-text)]">Settings</h1>
    <p className="max-w-3xl text-sm text-[var(--terminal-text-dim)]">
      Manage your account, workspace governance, model access, and platform controls.
    </p>
  </div>
</header>
```

**Step 3: Implement the overview cards with real links**

```tsx
<Button asChild variant="outline">
  <Link href="/settings/organization">Open Workspace & Access</Link>
</Button>

<Button asChild variant="outline">
  <Link href="/settings/api-keys">Open Developer Access</Link>
</Button>
```

**Step 4: Add the inline personal preferences section**

```tsx
const [preferences, setPreferences] = useState({
  compactMode: false,
  emailNotifications: true,
  desktopNotifications: true,
});
```

Use switches or button toggles only for local UI state in this pass. Do not add fake save calls.

**Step 5: Run the focused test**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: PASS for the overview-hub assertions.

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx frontend/src/components/layout/__tests__/SettingsPage.test.tsx
git commit -m "feat(settings): replace modal shell with overview hub"
```

### Task 3: Add valid App Router destinations for organization and API key settings

**Files:**
- Create: `frontend/app/(dashboard)/settings/organization/page.tsx`
- Create: `frontend/app/(dashboard)/settings/api-keys/page.tsx`
- Modify: `frontend/src/page-components/settings/OrganizationSettingsPage.tsx`
- Modify: `frontend/src/page-components/settings/APIKeyManagementPage.tsx`
- Create: `frontend/src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx`
- Create: `frontend/src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx`

**Step 1: Write the failing tests for the destination pages**

```tsx
it('renders workspace governance sections', () => {
  render(<OrganizationSettingsPage />);

  expect(screen.getByRole('heading', { name: 'Organization Settings' })).toBeInTheDocument();
  expect(screen.getByText('Members & Roles')).toBeInTheDocument();
  expect(screen.getByText('Usage & Billing')).toBeInTheDocument();
  expect(screen.getByText('Security & Compliance')).toBeInTheDocument();
});
```

```tsx
it('renders developer access sections', () => {
  render(<APIKeyManagementPage />);

  expect(screen.getByRole('heading', { name: 'API Key Management' })).toBeInTheDocument();
  expect(screen.getByText('Active Tokens')).toBeInTheDocument();
  expect(screen.getByText('Provider Access')).toBeInTheDocument();
  expect(screen.getByText('Rotation Guidance')).toBeInTheDocument();
});
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: FAIL because the components are still thin placeholders and no App Router route files exist yet.

**Step 3: Expand the page components into cohesive destination pages**

```tsx
export default function OrganizationSettingsPage() {
  return (
    <div className="space-y-6">
      <header>...</header>
      <section>{/* Members & Roles */}</section>
      <section>{/* Usage & Billing */}</section>
      <section>{/* Security & Compliance */}</section>
    </div>
  );
}
```

```tsx
export default function APIKeyManagementPage() {
  return (
    <div className="space-y-6">
      <header>...</header>
      <section>{/* Active Tokens */}</section>
      <section>{/* Provider Access */}</section>
      <section>{/* Rotation Guidance */}</section>
    </div>
  );
}
```

**Step 4: Add App Router wrappers that render those page components**

```tsx
import OrganizationSettingsPage from '@/page-components/settings/OrganizationSettingsPage';

export default function Page() {
  return <OrganizationSettingsPage />;
}
```

Mirror the pattern for `api-keys/page.tsx`.

**Step 5: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/organization/page.tsx frontend/app/\(dashboard\)/settings/api-keys/page.tsx frontend/src/page-components/settings/OrganizationSettingsPage.tsx frontend/src/page-components/settings/APIKeyManagementPage.tsx frontend/src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx frontend/src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx
git commit -m "feat(settings): add organization and api key destination pages"
```

### Task 4: Align visual treatment with NOUS brand and density guidance

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`
- Modify: `frontend/src/page-components/settings/OrganizationSettingsPage.tsx`
- Modify: `frontend/src/page-components/settings/APIKeyManagementPage.tsx`

**Step 1: Add explicit NOUS brand cues**

```tsx
<p className="text-xs font-mono uppercase tracking-[0.28em] text-[var(--phosphor-green)]">
  ACCESS_AND_GOVERNANCE
</p>
```

Use mono uppercase section labels sparingly for hierarchy. Keep body copy in standard UI type.

**Step 2: Standardize cards and density**

```tsx
className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
```

Avoid giant empty containers. Ensure each section contains enough summary information, bullets, or metadata rows to feel intentional.

**Step 3: Remove stale modal assumptions**

- no centered `settings-panel`
- no `router.back()` close button
- no tabbed account/usage/apps split on `/settings`

**Step 4: Run the focused settings tests**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx frontend/src/page-components/settings/OrganizationSettingsPage.tsx frontend/src/page-components/settings/APIKeyManagementPage.tsx
git commit -m "style(settings): align settings suite with NOUS brand system"
```

### Task 5: Validate type safety, linting, and route-level integrity

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx` if fixes are needed
- Modify: `frontend/src/page-components/settings/OrganizationSettingsPage.tsx` if fixes are needed
- Modify: `frontend/src/page-components/settings/APIKeyManagementPage.tsx` if fixes are needed

**Step 1: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS.

**Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: PASS with no new lint issues from the settings files.

**Step 3: Run focused tests**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: PASS.

**Step 4: Apply minimal cleanup if any check fails**

```tsx
// Fix only the failing typing, accessibility labels, imports, or query expectations.
```

**Step 5: Re-run all checks**

Run: `cd frontend && npm run type-check && npm run lint && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx frontend/src/components/layout/__tests__/SettingsPage.test.tsx frontend/app/\(dashboard\)/settings/organization/page.tsx frontend/app/\(dashboard\)/settings/api-keys/page.tsx frontend/src/page-components/settings/OrganizationSettingsPage.tsx frontend/src/page-components/settings/APIKeyManagementPage.tsx frontend/src/page-components/settings/__tests__/OrganizationSettingsPage.test.tsx frontend/src/page-components/settings/__tests__/APIKeyManagementPage.test.tsx
git commit -m "chore(settings): finalize overview hub validation"
```
