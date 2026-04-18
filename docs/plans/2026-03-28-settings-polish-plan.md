# Settings Overview Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Polish the `/settings` overview so it feels more premium and intentional by improving the hero, softening card CTAs, and fixing the self-linking profile card.

**Architecture:** Keep the current settings IA and route structure intact. Limit the work to presentation and small interaction refinements in the overview route, with test updates that define the new hero metadata and the profile-to-preferences jump behavior.

**Tech Stack:** Next.js 15 App Router, React 18, TypeScript, Tailwind CSS, lucide-react, shadcn/ui, Jest + Testing Library

**Execution skills:** `@test-driven-development`, `@vercel-react-best-practices`, `@verification-before-completion`

---

### Task 1: Update the settings route test for the polished hero and profile jump link

**Files:**
- Modify: `frontend/src/components/layout/__tests__/SettingsPage.test.tsx`

**Step 1: Write the failing test**

```tsx
expect(screen.getByText(/last sign-in/i)).toBeInTheDocument();
expect(screen.getByText(/audit active/i)).toBeInTheDocument();
expect(
  screen.getByRole('link', { name: /jump to personal controls/i })
).toHaveAttribute('href', '#personal-preferences');
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: FAIL because the current hero is sparse and the profile card still uses a route CTA.

**Step 3: Add one more assertion for reduced CTA heaviness**

```tsx
expect(
  screen.queryByRole('link', { name: /review profile & preferences/i })
).not.toBeInTheDocument();
```

**Step 4: Run test to verify it fails for the intended reasons**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: FAIL.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/__tests__/SettingsPage.test.tsx
git commit -m "test(settings): define hero polish and profile jump behavior"
```

### Task 2: Rebuild the top hero band and profile card action

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

**Step 1: Add richer hero metadata**

```tsx
const TRUST_ITEMS = ['Audit active', 'Encrypted', 'Admin access'];
```

Render:

- avatar/identity mark
- role badge
- workspace badge
- last sign-in text
- compact trust chips

**Step 2: Convert the first card CTA to an in-page jump**

```tsx
href: '#personal-preferences',
cta: 'Jump to personal controls',
```

Use a regular anchor link rather than a route link for this card.

**Step 3: Replace full-width outlined card buttons with lighter action rows**

```tsx
<Link className="inline-flex items-center gap-2 text-sm font-medium ...">
  {item.cta}
  <ArrowRight className="h-4 w-4" />
</Link>
```

**Step 4: Add bottom breathing room**

Increase route container bottom padding so the floating action button does not crowd the final row.

**Step 5: Run focused test**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx --runInBand`
Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx frontend/src/components/layout/__tests__/SettingsPage.test.tsx
git commit -m "style(settings): polish overview hero and card actions"
```

### Task 3: Verify the settings suite still holds after the visual pass

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx` if needed

**Step 1: Run focused settings tests**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx src/components/layout/__tests__/OrganizationSettingsPage.test.tsx src/components/layout/__tests__/APIKeyManagementPage.test.tsx --runInBand`
Expected: PASS.

**Step 2: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS.

**Step 3: Run targeted eslint**

Run: `cd frontend && npx eslint 'app/(dashboard)/settings/page.tsx' 'src/page-components/settings/OrganizationSettingsPage.tsx' 'src/page-components/settings/APIKeyManagementPage.tsx'`
Expected: PASS.

**Step 4: Apply minimal fixes if any check fails**

```tsx
// Fix only typing, naming, accessible labels, or link semantics introduced by the polish pass.
```

**Step 5: Re-run all three commands**

Run: `cd frontend && npm run test -- src/components/layout/__tests__/SettingsPage.test.tsx src/components/layout/__tests__/OrganizationSettingsPage.test.tsx src/components/layout/__tests__/APIKeyManagementPage.test.tsx --runInBand && npm run type-check && npx eslint 'app/(dashboard)/settings/page.tsx' 'src/page-components/settings/OrganizationSettingsPage.tsx' 'src/page-components/settings/APIKeyManagementPage.tsx'`
Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx frontend/src/components/layout/__tests__/SettingsPage.test.tsx
git commit -m "chore(settings): verify polished overview route"
```
