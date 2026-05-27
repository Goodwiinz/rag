# Vitest Migration — PR #2: Codemod Sweep + Remove Jest

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all 127 frontend test files from Jest to Vitest in a single mechanical sweep, remove Jest entirely, and flip the Vitest CI gate to required.

**Architecture:** Run `jest-codemods --transformer=vitest` across `frontend/src/**/__tests__/**` and `frontend/cli/__tests__/**` (96 files use Jest globals/APIs). Manually fix the ~15-20 files the codemod can't fully handle (timer mocks, `jest.requireActual`, `jest.isolateModules`, `jest.setTimeout`). Sweep three orphan tests with broken imports. Add `tsconfig.vitest.json` to fix Jest-types contamination flagged in PR #1 review. Widen the `vitest.workspace.mts` globs back to full coverage. Drop Jest deps, configs, and scripts. Make CI's `test-frontend-vitest` job required.

**Tech Stack:** Vitest 2.1, `jest-codemods`, `@testing-library/react` 14, jsdom 25, pnpm.

**Source design:** [docs/plans/2026-04-29-vitest-migration-design.md](./2026-04-29-vitest-migration-design.md)

**Predecessor:** PR #438 (PR #1: Vitest infra) — must be merged before starting this plan.

**Branch:** `chore/vitest-codemod` off `develop`

---

## Pre-flight

Run from repo root unless otherwise stated. Frontend uses **pnpm only**.

```bash
git checkout develop && git pull && git checkout -b chore/vitest-codemod
cd frontend && pnpm install --frozen-lockfile

# Verify PR #1 (Vitest infra) is merged into develop
test -f vitest.config.mts && echo "PR #1 present" || (echo "PR #1 not merged yet; STOP" && exit 1)
test -f vitest.workspace.mts || (echo "vitest.workspace.mts missing; STOP" && exit 1)

# Baseline test counts
find . -path '*/__tests__/*.test.*' -not -path '*/node_modules/*' -not -path '*/.next/*' -not -path '*/coverage/*' | wc -l   # ~127
pnpm test:vitest 2>&1 | tail -5   # smoke test should still pass (3/3)
```

If PR #1 isn't on `develop`, stop and merge it first.

---

## Task 1: Run jest-codemods Vitest preset

The codemod handles ~80% of mechanical changes: `jest.fn` → `vi.fn`, `jest.mock` → `vi.mock`, `jest.spyOn` → `vi.spyOn`, removes `import { jest } from '@jest/globals'`, etc.

**Files:** all 127 test files under `frontend/src/**/__tests__/**` and `frontend/cli/__tests__/**`.

**Step 1: Install the codemod**

```bash
cd frontend
pnpm dlx jest-codemods@latest --version   # confirm it resolves
```

**Step 2: Dry-run on a small sample**

```bash
pnpm dlx jest-codemods --parser=tsx --transformer=vitest --dry --print src/utils/__tests__/*.test.ts
```

Expected: shows what would change, no files modified. Eyeball the diffs for sanity.

**Step 3: Real run**

```bash
pnpm dlx jest-codemods --parser=tsx --transformer=vitest \
  'src/**/__tests__/**/*.test.{ts,tsx}' \
  'cli/__tests__/**/*.test.{ts,tsx}' \
  'src/__tests__/sanity.test.ts'
```

Expected: reports files modified count (~96 expected to change) and skipped count (~31 already Vitest-compatible or no changes needed).

**Step 4: Commit**

```bash
cd ..
git add 'frontend/src/**/__tests__/**/*.test.*' 'frontend/cli/__tests__/**/*.test.*' 'frontend/src/__tests__/sanity.test.ts'
git commit -m "test(frontend): codemod Jest → Vitest (jest-codemods sweep)"
```

---

## Task 2: Manual fixups for codemod misses

The codemod does not handle these patterns. They live in ~15-20 files. Audit and fix.

**Step 1: List files using each pattern**

```bash
cd frontend
echo "--- jest.useFakeTimers ---"
grep -rln "jest\.useFakeTimers" src cli --include='*.test.ts' --include='*.test.tsx'
echo "--- jest.requireActual ---"
grep -rln "jest\.requireActual" src cli --include='*.test.ts' --include='*.test.tsx'
echo "--- jest.isolateModules ---"
grep -rln "jest\.isolateModules" src cli --include='*.test.ts' --include='*.test.tsx'
echo "--- jest.setTimeout ---"
grep -rln "jest\.setTimeout" src cli --include='*.test.ts' --include='*.test.tsx'
echo "--- residual 'jest.' references ---"
grep -rn "\\bjest\\." src cli --include='*.test.ts' --include='*.test.tsx' | grep -v '@testing-library/jest-dom'
```

Each command's output should ideally be empty after Task 1, but won't be for the patterns above.

**Step 2: Apply manual fixups per pattern**

For each file the grep flagged, edit by hand using these mappings:

| Jest                                   | Vitest                                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `jest.useFakeTimers('modern')`         | `vi.useFakeTimers()` (modern is default)                                                                      |
| `jest.useFakeTimers({ now: 123 })`     | `vi.useFakeTimers({ now: 123 })`                                                                              |
| `jest.requireActual('foo')`            | `await vi.importActual('foo')` (note: now async — wrap call site in async fn)                                 |
| `jest.isolateModules(() => { ... })`   | `await vi.isolateModulesAsync(async () => { ... })`                                                           |
| `jest.setTimeout(30_000)`              | Replace with per-test `{ timeout: 30_000 }` option, or set globally in `vitest.config.mts` `test.testTimeout` |
| `import { jest } from '@jest/globals'` | `import { vi } from 'vitest'`                                                                                 |

If a file imports `vi` but the codemod still left `jest` as a runtime reference (rare), replace `jest.` with `vi.` at the call site.

**Step 3: Run Vitest on each batch as you fix**

```bash
pnpm exec vitest run src/utils/__tests__/supabase-client.test.ts
# fix, re-run, repeat
```

**Step 4: Final sweep — confirm no `jest.` runtime references remain**

```bash
grep -rn '\bjest\.' src cli --include='*.test.ts' --include='*.test.tsx' | grep -v '@testing-library/jest-dom'
```

Expected: empty output.

**Step 5: Commit**

```bash
cd ..
git add frontend/src frontend/cli
git commit -m "test(frontend): manual fixups for jest-codemods misses (timers, requireActual, isolateModules)"
```

---

## Task 3: Orphan test sweep

Three CLI tests have broken imports — their source modules don't exist in the current tree.

**Files (each is one of):** fix or delete.

```
frontend/cli/__tests__/errors.test.ts          → expects ../errors
frontend/cli/__tests__/retry.test.ts           → expects ../retry
frontend/cli/__tests__/services/draft.test.ts  → expects ../../services/draft
```

**Step 1: For each, locate the source**

```bash
cd frontend
for path in errors retry services/draft; do
  echo "=== $path ==="
  find cli -type f \( -name "${path##*/}.ts" -o -name "${path##*/}.tsx" \) -not -path '*/node_modules/*' -not -path '*/__tests__/*'
done
```

Expected: empty output for all three (sources are dead).

**Step 2: Verify nothing else references them**

```bash
grep -rn "from '\\.\\./errors'\\|from '\\.\\./retry'\\|from '\\.\\./\\.\\./services/draft'" cli src 2>/dev/null
```

If any non-test file imports them, the source isn't dead — restore it. If only the test files reference them, delete the tests.

**Step 3: Delete dead tests**

```bash
git rm cli/__tests__/errors.test.ts cli/__tests__/retry.test.ts cli/__tests__/services/draft.test.ts
```

**Step 4: Commit**

```bash
cd ..
git commit -m "test(frontend): remove orphan tests with dead imports (errors, retry, services/draft)"
```

If any of the three sources turned out to exist (different filename, different path), instead fix the import in the test and commit:

```bash
git commit -m "test(frontend): fix orphan test imports after source rename"
```

---

## Task 4: Add `tsconfig.vitest.json` to fix types contamination

Reviewer flagged: `frontend/tsconfig.test.json` injects `"jest"` into `types`, and its `include` covers `src/test/**` — meaning Vitest tests get Jest globals types. Risk: a developer writes `expect()` without import, TS resolves to Jest's type, runtime fails under Vitest.

**Files:**

- Create: `frontend/tsconfig.vitest.json`
- Modify: `frontend/vitest.config.mts` (point typecheck at the new tsconfig)

**Step 1: Read current tsconfig.test.json**

```bash
cat frontend/tsconfig.test.json
```

**Step 2: Create `frontend/tsconfig.vitest.json`** that extends the base but excludes `"jest"` from `types`:

```json
{
  "extends": "./tsconfig.test.json",
  "compilerOptions": {
    "types": ["vitest/globals", "node", "@testing-library/jest-dom/vitest"]
  },
  "include": ["src/test/**/*", "src/**/__tests__/**/*", "cli/__tests__/**/*"]
}
```

(Adjust `include` to match what the codebase actually wants typed; the above is a safe superset.)

**Step 3: Update `frontend/vitest.config.mts`** to add typecheck config:

```ts
test: {
  // … existing fields …
  typecheck: {
    tsconfig: './tsconfig.vitest.json',
  },
},
```

**Step 4: Verify type-check still clean**

```bash
cd frontend && pnpm exec tsc --noEmit -p tsconfig.vitest.json 2>&1 | head -30
```

Expected: no errors specific to test files. Pre-existing errors elsewhere are out of scope.

**Step 5: Commit**

```bash
cd ..
git add frontend/tsconfig.vitest.json frontend/vitest.config.mts
git commit -m "chore(frontend): add tsconfig.vitest.json (excludes jest types from vitest scope)"
```

---

## Task 5: Reintroduce shared mocks in `src/test/setup.ts` if needed

PR #1 dropped 4 mocks from `src/test/setup.ts` (orphan content): IntersectionObserver, ResizeObserver, matchMedia, WebSocket. Existing component tests polyfill these locally. After codemod, run the suite — if many tests fail because of missing globals, centralize them.

**Step 1: Run the full Vitest suite (still narrowed to smoke test in `vitest.workspace.mts`)**

First, temporarily widen the unit glob to discover failures:

```bash
cd frontend
sed -i.bak "s|'src/test/__tests__/\*\*/\*\.test\.{ts,tsx}'|'src/**/__tests__/**/*.test.{ts,tsx}'|" vitest.workspace.mts
pnpm exec vitest run 2>&1 | tee /tmp/vitest-discovery.log | tail -50
mv vitest.workspace.mts.bak vitest.workspace.mts
```

(The `.bak` restore reverts so we don't commit the widened glob until Task 6.)

**Step 2: Check if mocks are needed**

```bash
grep -E "IntersectionObserver|ResizeObserver|matchMedia|WebSocket" /tmp/vitest-discovery.log | head
```

If the log shows multiple files failing with `is not defined` for those globals, add the mocks centrally. If only 1-2 files fail, leave them as local polyfills (already present in `src/components/__tests__/testUtils.tsx` etc.).

**Step 3: If centralizing — append to `frontend/src/test/setup.ts`**

```ts
// jsdom doesn't ship these — components using Radix popovers, scroll-into-view,
// prefers-color-scheme media queries, or WS clients need them.
class MockIntersectionObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}
class MockResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

const gx = globalThis as unknown as {
  IntersectionObserver?: typeof globalThis.IntersectionObserver;
  ResizeObserver?: typeof globalThis.ResizeObserver;
  matchMedia?: typeof window.matchMedia;
  WebSocket?: typeof globalThis.WebSocket;
};

if (typeof gx.IntersectionObserver === "undefined") {
  gx.IntersectionObserver =
    MockIntersectionObserver as unknown as typeof globalThis.IntersectionObserver;
}
if (typeof gx.ResizeObserver === "undefined") {
  gx.ResizeObserver =
    MockResizeObserver as unknown as typeof globalThis.ResizeObserver;
}
if (typeof window !== "undefined" && typeof window.matchMedia === "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
// WebSocket only if a test imports a WS client. Skip unless needed.
```

**Step 4: Commit (only if you added the mocks)**

```bash
cd ..
git add frontend/src/test/setup.ts
git commit -m "test(frontend): centralize IntersectionObserver/ResizeObserver/matchMedia mocks for jsdom"
```

If no centralization was needed, skip this commit.

---

## Task 6: Widen `vitest.workspace.mts` globs

Now that all 127 tests are Vitest-compatible, restore full coverage.

**Files:**

- Modify: `frontend/vitest.workspace.mts`

**Step 1: Update both project includes**

Change:

```ts
include: ['src/test/__tests__/**/*.test.{ts,tsx}'],
```

to:

```ts
include: ['src/**/__tests__/**/*.test.{ts,tsx}', 'src/__tests__/sanity.test.ts'],
exclude: [
  'src/integration/**',
  'src/__tests__/App.routing.test.tsx',  // re-enabled in Task 8
  'node_modules/**',
  'e2e/**',
],
```

For the `cli` project, change:

```ts
include: ['cli/__tests__/__vitest_only__/**/*.test.{ts,tsx}'],
```

to:

```ts
include: ['cli/__tests__/**/*.test.{ts,tsx}'],
```

**Step 2: Run the full suite**

```bash
cd frontend && pnpm test:vitest 2>&1 | tail -20
```

Expected: all tests pass (124 after orphan deletion). If any fail, fix under Task 2 or Task 5; do not weaken the glob.

**Step 3: Commit**

```bash
cd ..
git add frontend/vitest.workspace.mts
git commit -m "chore(frontend): widen vitest workspace globs to full test surface"
```

---

## Task 7: Improve smoke test alias assertion

PR #1 reviewer flagged: `vitest-smoke.test.ts`'s alias test asserts `typeof mod === 'object'` (always true). Change to a known named export check so silent alias drift is caught.

**Files:**

- Modify: `frontend/src/test/__tests__/vitest-smoke.test.ts`

**Step 1: Update the alias test**

Current:

```ts
it("can import a TS path alias", async () => {
  const mod = await import("@/types/schemas");
  expect(typeof mod).toBe("object");
});
```

New (check for an export that lives only in `src/types/schemas.ts`):

```ts
it("can import a TS path alias and resolves to src/, not app/", async () => {
  const mod = await import("@/types/schemas");
  // DocumentSchema is defined in src/types/schemas.ts; if @/* ever
  // silently re-resolves to app/, this assertion catches it.
  expect(mod.DocumentSchema).toBeDefined();
  expect(typeof mod.DocumentSchema.parse).toBe("function");
});
```

(If `DocumentSchema` isn't an export, substitute any other named Zod schema actually exported from that file.)

**Step 2: Run**

```bash
cd frontend && pnpm exec vitest run src/test/__tests__/vitest-smoke.test.ts
```

Expected: 3 passed.

**Step 3: Commit**

```bash
cd ..
git add frontend/src/test/__tests__/vitest-smoke.test.ts
git commit -m "test(frontend): tighten vitest smoke alias assertion to named export"
```

---

## Task 8: Re-enable `App.routing.test.tsx`

Jest's config currently ignores this file (`testPathIgnorePatterns: [..., 'App\\.routing\\.test\\.tsx$']`). Vitest doesn't need that carve-out unless the test itself is broken.

**Step 1: Try running it on Vitest**

```bash
cd frontend && pnpm exec vitest run src/__tests__/App.routing.test.tsx 2>&1 | tail -30
```

**Step 2: Decide based on result**

- **Passes:** great — it works under Vitest. Remove the `exclude` entry from `vitest.workspace.mts` (added in Task 6) and commit.
- **Fails:** read the failure. If it's a real bug in the test, fix it. If the test is dead/obsolete, delete it.

**Step 3: Commit (one of)**

```bash
# If passing, removed from exclude:
git commit -am "test(frontend): re-enable App.routing.test.tsx under Vitest"
# Or if dead:
git rm frontend/src/__tests__/App.routing.test.tsx
git commit -m "test(frontend): remove dead App.routing.test.tsx"
```

---

## Task 9: Remove Jest dependencies

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`

**Step 1: Remove Jest deps**

```bash
cd frontend
pnpm remove jest ts-jest jest-junit jest-html-reporters jest-environment-jsdom identity-obj-proxy @types/jest jest-circus 2>&1 | tail -10
```

(`@testing-library/jest-dom` STAYS — it's framework-agnostic and we use the `/vitest` entry.)

**Step 2: Verify**

```bash
grep -E '"(jest|ts-jest|jest-junit|jest-html-reporters|jest-environment-jsdom|identity-obj-proxy|@types/jest|jest-circus)":' package.json
```

Expected: empty output.

**Step 3: Commit**

```bash
cd ..
git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): remove Jest dependencies (jest, ts-jest, jest-junit, jest-html-reporters, jest-environment-jsdom, identity-obj-proxy, @types/jest, jest-circus)"
```

---

## Task 10: Delete Jest config and setup files

**Files:**

- Delete: `frontend/jest.config.js`
- Delete: `frontend/src/setupTests.ts`

**Step 1: Confirm nothing imports them**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr2-plan
grep -rn 'jest.config\\|setupTests' frontend --include='*.ts' --include='*.tsx' --include='*.js' --include='*.json' 2>/dev/null | grep -v node_modules
```

Expected: nothing references them at runtime. Old `package.json` script entries will appear — those are fixed in Task 11.

**Step 2: Delete**

```bash
git rm frontend/jest.config.js frontend/src/setupTests.ts
```

**Step 3: Commit**

```bash
git commit -m "chore(frontend): delete jest.config.js and src/setupTests.ts"
```

---

## Task 11: Rewrite `package.json` scripts

**Files:**

- Modify: `frontend/package.json`

**Step 1: Replace Jest-based scripts**

Open `frontend/package.json` and update the `scripts` block:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest run --coverage",
    "...": "..."
  }
}
```

Specifically:

- `"test": "jest"` → `"test": "vitest run"`
- `"test:watch": "jest --watch"` → `"test:watch": "vitest"`
- `"test:coverage": "jest --coverage"` → `"test:coverage": "vitest run --coverage"`
- Remove the `test:vitest`, `test:vitest:watch`, `test:vitest:ui`, `test:vitest:coverage` aliases — consolidated into the canonical names above.
- `"test:unit": "jest src/**/*.{test,spec}.{ts,tsx}"` → delete (covered by `test`)
- `"test:integration": "jest src/**/*.integration.{test,spec}.{ts,tsx}"` → `"test:integration": "vitest run src/integration"` (or delete if integration tests live under `src/integration/__tests__/`)
- `"test:component": "jest src/**/*.{test,spec}.{ts,tsx}"` → delete (duplicate of `test`)

**Step 2: Verify**

```bash
cd frontend
grep -E '"test' package.json
pnpm test 2>&1 | tail -10   # should now run Vitest
```

Expected: `pnpm test` runs Vitest and tests pass.

**Step 3: Commit**

```bash
cd ..
git add frontend/package.json
git commit -m "chore(frontend): consolidate test scripts on Vitest (drop test:vitest aliases)"
```

---

## Task 12: Verify no `next/jest` references

`next/jest` was only referenced in `jest.config.js` (deleted in Task 10), but verify nothing else uses it.

**Step 1: Search**

```bash
grep -rn "next/jest" frontend --include='*.ts' --include='*.tsx' --include='*.js' --include='*.mts' --include='*.json' 2>/dev/null | grep -v node_modules
```

Expected: empty output.

**Step 2: Remove from package.json if present**

If `next/jest` is listed as a dependency:

```bash
cd frontend && pnpm remove next/jest 2>&1 | tail -5
```

(It's typically not a separate package — comes with `next` itself — so this is usually a no-op.)

**Step 3: Commit only if changes were made**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): drop next/jest references"
```

---

## Task 13: Drop `craco.config.js` if unused

`craco` predates Next.js. Likely dead.

**Step 1: Check usage**

```bash
grep -rn "craco" frontend --include='*.ts' --include='*.tsx' --include='*.js' --include='*.json' 2>/dev/null | grep -v node_modules | grep -v '/coverage/'
```

If results show only `craco.config.js` itself and `package.json` script entries calling `craco`, it's dead.

If `package.json` has any `"start": "craco start"` or similar, those are dead Create-React-App holdovers — Next.js apps use `next dev`.

**Step 2: If dead — delete**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr2-plan
git rm frontend/craco.config.js
# Also remove any "craco" scripts from package.json (manual edit)
```

**Step 3: Commit**

```bash
git add frontend/package.json
git commit -m "chore(frontend): remove dead craco config and scripts"
```

If craco IS in use somewhere (unlikely for a Next.js app), skip this task and note for a future cleanup.

---

## Task 14: CI — make Vitest required, drop npm-based job

**Files:**

- Modify: `.github/workflows/fast-ci.yml`

**Step 1: Bump pnpm version + flip continue-on-error**

In the `test-frontend-vitest` job:

- Change `version: 9` → `version: 10` in the `pnpm/action-setup` step (matches lockfile generator)
- Remove `continue-on-error: true` (or set to `false`)
- Update the inline comment from "PR #1 only" to "required"

**Step 2: Drop the npm-based `test-frontend` job**

The original `test-frontend` job uses `npm install`/`npm test`. Now that Vitest is the test runner and pnpm is the only package manager, this job is misleading and incorrect. Either delete it entirely, or rewrite it to mirror `test-frontend-vitest` (but that would be redundant). Delete is simplest.

Update the `summary` job's `needs:` accordingly:

```yaml
needs: [lint, test-backend, test-frontend-vitest]
```

**Step 3: Add Vitest result echo to summary**

In the `summary` job's run script, add:

```yaml
echo "Frontend Tests (Vitest): ${{ needs.test-frontend-vitest.result }}" >> "$GITHUB_STEP_SUMMARY"
```

So a regression is visible at a glance.

**Step 4: Add `packageManager` field to package.json (alternative or supplement to bumping action-setup)**

```bash
cd frontend
node -e "const p=require('./package.json'); p.packageManager='pnpm@10.33.0'; require('fs').writeFileSync('./package.json', JSON.stringify(p, null, 2) + '\n');"
```

This lets `pnpm/action-setup@v4` infer the version automatically and prevents future drift.

**Step 5: Validate YAML and commit**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr2-plan
python3 -c 'import yaml; yaml.safe_load(open(".github/workflows/fast-ci.yml")); print("OK")'
git add .github/workflows/fast-ci.yml frontend/package.json
git commit -m "ci(frontend): make Vitest job required, drop npm-based test job, surface result in summary"
```

---

## Task 15: Final verification

**Step 1: Full Vitest run**

```bash
cd frontend && pnpm test 2>&1 | tail -20
```

Expected: all tests pass, count matches `find . -path '*/__tests__/*.test.*' -not -path '*/node_modules/*' | wc -l`.

**Step 2: Coverage**

```bash
pnpm test:coverage 2>&1 | tail -20
ls coverage/lcov.info coverage/coverage-summary.json
```

Expected: passes; both files exist; coverage figures are real (not 0%).

**Step 3: No residual Jest references**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr2-plan
grep -rEn "(\\bjest\\b|jest\\.config|setupTests|next/jest|ts-jest|jest-junit|jest-html-reporters|jest-environment-jsdom|identity-obj-proxy|jest-circus)" frontend --include='*.ts' --include='*.tsx' --include='*.js' --include='*.mts' --include='*.json' --include='*.yml' 2>/dev/null | grep -v node_modules | grep -v '/coverage/' | grep -v '@testing-library/jest-dom'
```

Expected: empty output. The only acceptable matches are `@testing-library/jest-dom` (intentionally kept) and any docs in `docs/plans/`.

**Step 4: Type check**

```bash
cd frontend && pnpm type-check 2>&1 | tail -10
```

Expected: no new errors.

**Step 5: Lint**

```bash
pnpm lint 2>&1 | tail -10
```

Expected: same baseline as `develop`.

If anything fails, fix and create a follow-up commit. Do not proceed to the PR until this task is fully green.

---

## Task 16: Open the PR

**Step 1: Push**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr2-plan
git push -u origin chore/vitest-codemod
```

**Step 2: Open PR**

```bash
gh pr create --base develop --title "chore(frontend): migrate Jest → Vitest (PR 2/5)" --body "$(cat <<'EOF'
## Summary

Part 2 of 5 of the Vitest migration ([design](./docs/plans/2026-04-29-vitest-migration-design.md), [PR #2 plan](./docs/plans/2026-04-29-vitest-pr2-codemod.md)).

This PR migrates **all 127 frontend test files** from Jest to Vitest in a single mechanical sweep, removes Jest entirely, and makes the Vitest CI gate required.

### Highlights

- `jest-codemods --transformer=vitest` rewrote ~96 files; ~15 had manual fixups for `jest.useFakeTimers`/`jest.requireActual`/`jest.isolateModules`/`jest.setTimeout`
- Three orphan tests with broken imports removed (`cli/__tests__/errors.test.ts`, `retry.test.ts`, `services/draft.test.ts`)
- New `tsconfig.vitest.json` excludes `"jest"` from `types`, fixing the type-contamination flagged in PR #1 review
- Workspace globs widened back to full coverage; `App.routing.test.tsx` re-enabled (or deleted)
- Smoke test now asserts a known named export, not just `typeof === 'object'`
- Jest deps removed: `jest`, `ts-jest`, `jest-junit`, `jest-html-reporters`, `jest-environment-jsdom`, `identity-obj-proxy`, `@types/jest`, `jest-circus`
- `frontend/jest.config.js` and `frontend/src/setupTests.ts` deleted
- `package.json` scripts: `test` → `vitest run`; aliases consolidated
- `craco.config.js` deleted (verified dead)
- CI: `test-frontend-vitest` is now required (`continue-on-error: false`); `pnpm/action-setup` bumped to v10; `packageManager` field added; the npm-based `test-frontend` job removed; summary echoes the Vitest result

### Out of scope (next PRs)

- PR #3: MSW standardization with `onUnhandledRequest: 'error'`
- PR #4: Zod-validated test fixtures
- PR #5: coverage ratchet to 50/40/45/50

## Test plan

- [ ] CI green: `test-frontend-vitest` passes
- [ ] `pnpm test` locally: all tests pass
- [ ] `pnpm test:coverage` produces lcov.info with non-zero coverage
- [ ] No `jest` references in `frontend/` (except `@testing-library/jest-dom`)
- [ ] No `npm` commands in CI (pnpm only)
EOF
)"
```

**Step 3: Watch CI**

```bash
gh pr checks --watch
```

---

## Definition of done for PR #2

- [ ] All 16 tasks committed
- [ ] PR opened against `develop`
- [ ] CI green; `test-frontend-vitest` is the required check (no longer `continue-on-error`)
- [ ] `frontend/jest.config.js` and `frontend/src/setupTests.ts` no longer exist
- [ ] `pnpm test` runs Vitest by default
- [ ] No Jest dependencies in `package.json` (other than `@testing-library/jest-dom`)
- [ ] `tsconfig.vitest.json` exists; Vitest typecheck uses it
- [ ] All 124 tests pass on Vitest (127 minus 3 orphans)
- [ ] Coverage reports produced (lcov.info, coverage-summary.json)
- [ ] No `next/jest`, no `craco`, no `@types/jest` references in source
- [ ] Workspace globs cover full `src/**/__tests__/**` and `cli/__tests__/**`
- [ ] CI summary echoes `${{ needs.test-frontend-vitest.result }}`

---

## Follow-up plans

- `docs/plans/<date>-vitest-pr3-msw.md` — write after PR #2 merges. Standardize MSW: split `src/mocks/server.ts` by domain, set `onUnhandledRequest: 'error'`, add ESLint rule banning `global.fetch = vi.fn()` in tests, audit and remove ad-hoc fetch/axios mocks across all 124 tests.
- `docs/plans/<date>-vitest-pr4-zod-fixtures.md` — write after PR #3 merges. Add `defineFixture(schema, data)` helper that validates against existing Zod schemas; convert top 5 fixtures (User, Document, Thread, Message, Project).
- `docs/plans/<date>-vitest-pr5-coverage-ratchet.md` — write after PR #4 merges. Bump thresholds to 50/40/45/50 on `services`/`hooks`/`utils`; add tests for any module below threshold; remove the temporary 0/0/0/0 thresholds set in PR #1.

Each will follow this same bite-sized template, anchored to the [design doc](./2026-04-29-vitest-migration-design.md).
