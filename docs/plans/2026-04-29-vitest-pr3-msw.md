# Vitest Migration — PR #3: MSW Standardization

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make MSW the single network mocking surface for all frontend tests. Set `onUnhandledRequest: 'error'`. Kill ad-hoc `global.fetch = vi.fn()` and per-test `mockResolvedValue` of fake Response objects. Add an ESLint rule that enforces this.

**Architecture:** Split the 526-line monolithic `frontend/src/mocks/server.ts` into per-domain handler files under `frontend/src/test/msw/handlers/`. Wire `setupServer()` lifecycle into `frontend/src/test/setup.ts` (`listen` → `resetHandlers` → `close`). Sweep all tests that mock the network ad-hoc and replace them with handler overrides via `server.use(...)`. Add an ESLint custom rule (or generic `no-restricted-syntax`) that bans `global.fetch =` patterns inside `*.test.*` files.

**Tech Stack:** MSW 2.13 (already installed), Vitest 2.1, ESLint, pnpm.

**Source design:** [docs/plans/2026-04-29-vitest-migration-design.md](./2026-04-29-vitest-migration-design.md)

**Predecessor:** PR #443 (PR #2: codemod sweep) **and all its follow-up failure-fix PRs** must merge first. This plan assumes `pnpm test` (Vitest) is fully green on `develop`.

**Branch:** `chore/vitest-msw` off `develop`

---

## Pre-flight

```bash
git checkout develop && git pull && git checkout -b chore/vitest-msw
cd frontend && pnpm install --frozen-lockfile

# Verify PR #2 (codemod) and follow-ups are merged: full Vitest suite green
pnpm test 2>&1 | tail -5   # must show "0 failed" or equivalent green state

# Confirm MSW already present
grep '"msw":' package.json   # expect ^2.13.x
ls src/mocks/server.ts       # expect the 526-line monolith
```

If any test fails at this baseline, **stop**. PR #3 must start from a green tree.

---

## Survey (record actual numbers as you go — your inventory)

```bash
# Files using direct fetch overrides
grep -rlE "(global|window|globalThis)\\.fetch\\s*=" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null

# Files mocking Response objects via vi.fn / mockResolvedValue / mockReturnValue
grep -rlE "mock(Resolved|Returned|Implementation).*Response|new Response\\(|\\bResponse\\.json\\(" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null

# Existing handler count in monolith
grep -c "http\\.(get|post|put|delete|patch)\\(" src/mocks/server.ts
```

Expected today (snapshot from `develop` at planning time): ~2 files with global fetch overrides, ~9 files with Response/network mocking patterns, ~22 handlers in the monolith.

---

## Task 1: Move MSW server lifecycle into Vitest setup

The MSW server currently exists at `src/mocks/server.ts` but is not wired into Vitest's setup file (`src/test/setup.ts` doesn't call `server.listen()`). Tests that import it manage the lifecycle themselves, which is brittle.

**Files:**

- Modify: `frontend/src/test/setup.ts`
- Create: `frontend/src/test/msw/server.ts` (re-exports the test-only server)

**Step 1: Create the test-only server**

```ts
// frontend/src/test/msw/server.ts
// Test-only MSW server. Production code must NEVER import this.
// Handlers live in ./handlers/index.ts (split per domain in Task 2).
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

`./handlers` doesn't exist yet — Task 2 creates it. For PR #3 Task 1, create a temporary placeholder:

```ts
// frontend/src/test/msw/handlers/index.ts (placeholder; expanded in Task 2)
export const handlers = [];
```

**Step 2: Wire lifecycle into `src/test/setup.ts`**

Append to `frontend/src/test/setup.ts`:

```ts
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

beforeAll(() => {
  // 'error' makes any unmocked network call fail loudly. Tests must
  // either route through MSW handlers or override per-test via server.use().
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  // Reset per-test handler overrides so tests don't leak state.
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
```

**Step 3: Verify the smoke test still passes**

```bash
cd frontend && pnpm test src/test/__tests__/vitest-smoke.test.ts 2>&1 | tail -5
```

Expected: 3 passed. The smoke test doesn't make network calls, so `onUnhandledRequest: 'error'` doesn't fire.

**Step 4: Commit**

```bash
cd ..
git add frontend/src/test/setup.ts frontend/src/test/msw/server.ts frontend/src/test/msw/handlers/index.ts
git commit -m "test(frontend): wire MSW server lifecycle into vitest setup (onUnhandledRequest: error)"
```

After this commit, the full suite will likely **fail** because tests that hit the network without going through MSW now error. That's expected — Tasks 2 and 3 fix it.

---

## Task 2: Split `src/mocks/server.ts` into per-domain handlers

The monolithic 526-line file mixes auth, documents, search, evaluation, and other domains. Splitting makes review easier and lets handler files own their domain types.

**Files:**

- Create: `frontend/src/test/msw/handlers/auth.ts`
- Create: `frontend/src/test/msw/handlers/documents.ts`
- Create: `frontend/src/test/msw/handlers/search.ts`
- Create: `frontend/src/test/msw/handlers/threads.ts`
- Create: `frontend/src/test/msw/handlers/evaluation.ts`
- Create: `frontend/src/test/msw/handlers/projects.ts`
- Create: `frontend/src/test/msw/handlers/index.ts` (re-export aggregated array)
- Modify (then delete): `frontend/src/mocks/server.ts`

**Step 1: Read the monolith and inventory handlers**

```bash
cd frontend
grep -n "http\\.(get|post|put|delete|patch)\\(" src/mocks/server.ts
```

Group results by URL prefix:

- `/api/v1/auth/*` → `auth.ts`
- `/api/v1/documents*` → `documents.ts`
- `/api/v1/search*` → `search.ts`
- `/api/v1/threads*` → `threads.ts`
- `/api/v1/evaluation*` → `evaluation.ts`
- `/api/v1/projects*` → `projects.ts`
- everything else → `misc.ts` (avoid this if possible — better to put it in the closest domain)

**Step 2: For each domain, create the handler file**

Pattern (auth as an example):

```ts
// frontend/src/test/msw/handlers/auth.ts
import { http, HttpResponse, delay } from "msw";

export const authHandlers = [
  http.post("/api/v1/auth/login", async ({ request }) => {
    const body = (await request.json()) as {
      email?: string;
      password?: string;
    };
    if (body.email === "fail@example.com") {
      return HttpResponse.json(
        {
          error: {
            message: "Invalid credentials",
            status_code: 401,
            type: "auth_error",
            timestamp: new Date().toISOString(),
          },
        },
        { status: 401 },
      );
    }
    return HttpResponse.json({
      token: "test-token",
      user: { id: "u-1", email: body.email ?? "demo@example.com" },
    });
  }),
  // … other auth routes
];
```

Repeat for each domain. Cut and paste from `src/mocks/server.ts` and clean up. Keep the helper data generators (`createMockDocument`, etc.) — move them adjacent to the handlers that use them, or into a shared `frontend/src/test/msw/fixtures/` module if multiple handler files need them. Prefer co-location to a shared module unless the data is genuinely shared.

**Step 3: Aggregate**

```ts
// frontend/src/test/msw/handlers/index.ts
import { authHandlers } from "./auth";
import { documentsHandlers } from "./documents";
import { searchHandlers } from "./search";
import { threadsHandlers } from "./threads";
import { evaluationHandlers } from "./evaluation";
import { projectsHandlers } from "./projects";

export const handlers = [
  ...authHandlers,
  ...documentsHandlers,
  ...searchHandlers,
  ...threadsHandlers,
  ...evaluationHandlers,
  ...projectsHandlers,
];
```

**Step 4: Delete the monolith**

```bash
git rm src/mocks/server.ts
```

If anything outside tests imports `src/mocks/server.ts`, find and update it:

```bash
grep -rn "from '@/mocks/server'\\|from '\\.\\./mocks/server'\\|from '\\.\\./\\.\\./mocks/server'" src cli --include='*.ts' --include='*.tsx'
```

Expected: only test files. If any non-test file imports it, the previous setup leaked test code into production — flag and fix in this commit.

**Step 5: Run a sample test that hits MSW**

Pick any service test that calls a mocked endpoint:

```bash
pnpm test src/services/__tests__/api-client.test.ts 2>&1 | tail -20
```

Expected: passes. If it fails with "request not handled" then your handlers don't cover the URL — add it to the appropriate domain file.

**Step 6: Commit**

```bash
cd ..
git add frontend/src/test/msw/handlers frontend/src/mocks
git commit -m "test(frontend): split MSW handlers per domain (auth, documents, search, threads, evaluation, projects)"
```

---

## Task 3: Replace ad-hoc fetch mocks with MSW

Tests using `global.fetch = vi.fn()` or `mockResolvedValue(new Response(...))` patterns must be rewritten. With `onUnhandledRequest: 'error'` from Task 1, they will already be failing CI — so this task is the fix.

**Step 1: List the offending files**

```bash
cd frontend
echo "=== global fetch overrides ==="
grep -rlE "(global|window|globalThis)\\.fetch\\s*=" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null

echo "=== Response object mocks ==="
grep -rlE "mockResolvedValue.*Response|mockReturnValue.*Response|new Response\\(|fetchMock|jest\\.fn\\(\\).*fetch" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null

echo "=== axios mocks ==="
grep -rlE "vi\\.mock\\(['\"]axios['\"]\\)|axios\\.create.*mock" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null
```

Expected (rough): ~2 files with global fetch overrides, ~9 with Response patterns, ~3 with axios mocks. Numbers will shift between planning and execution — record what you actually find.

**Step 2: Conversion pattern**

Old:

```ts
beforeEach(() => {
  global.fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ token: "abc" }), { status: 200 }),
    );
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("logs in", async () => {
  const result = await login({ email: "a@b.com", password: "pw" });
  expect(result.token).toBe("abc");
});
```

New:

```ts
import { http, HttpResponse } from "msw";
import { server } from "@/test/msw/server";

it("logs in", async () => {
  // Default handler in src/test/msw/handlers/auth.ts already returns
  // { token: 'test-token' } for /api/v1/auth/login.
  // Override here only if THIS test needs different data.
  server.use(
    http.post("/api/v1/auth/login", () => HttpResponse.json({ token: "abc" })),
  );

  const result = await login({ email: "a@b.com", password: "pw" });
  expect(result.token).toBe("abc");
});
```

Key points:

- **Per-test overrides via `server.use(...)`** — MSW prepends them to the handler list; `afterEach` resets them via `server.resetHandlers()`.
- **No `vi.restoreAllMocks` needed** — there's no mock to restore.
- **Use the imported `http` / `HttpResponse` from `msw`** — same imports the handler files use.

**Step 3: Sweep file-by-file**

For each file from Step 1:

1. Open it.
2. Identify what URLs / endpoints it mocks.
3. Confirm there's a corresponding handler in `src/test/msw/handlers/`. If not, add a default handler there.
4. Replace the ad-hoc mock with `server.use(...)` overrides — only if the test needs a non-default response.
5. Run the file: `pnpm test path/to/file.test.ts`.
6. If it passes, move on. If not, debug — usually it's a URL-mismatch (handler covers `/api/v1/foo` but the code calls `/api/foo`).

Commit after each ~5 files to keep the PR reviewable and bisectable:

```bash
cd ..
git add frontend/src/services/__tests__/agentChatService.test.ts frontend/src/services/__tests__/api-client.auth.test.ts
git commit -m "test(frontend): replace ad-hoc fetch mocks with MSW (auth + agent-chat services)"
```

Repeat for batches of related files.

**Step 4: Final verification**

```bash
cd frontend
echo "=== should be empty ==="
grep -rE "(global|window|globalThis)\\.fetch\\s*=" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null
grep -rlE "mockResolvedValue.*Response|new Response\\(|fetchMock" src cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null

pnpm test 2>&1 | tail -10
```

Both grep commands should produce no output. Vitest must be 100% green.

---

## Task 4: Add ESLint rule banning ad-hoc fetch mocks

Prevents regressions. Future PRs that try to write `global.fetch = vi.fn()` get blocked at lint time.

**Files:**

- Modify: `frontend/.eslintrc.json` (or `eslint.config.{js,mjs}` — read first to see which is in use)

**Step 1: Inspect current ESLint config**

```bash
cd frontend
ls .eslintrc.json eslint.config.{js,mjs,cjs,ts} 2>/dev/null
```

**Step 2: Add a `no-restricted-syntax` rule scoped to test files**

Add to the relevant ESLint config under `overrides` (or the equivalent for flat config):

```json
{
  "overrides": [
    {
      "files": [
        "src/**/__tests__/**/*.{ts,tsx}",
        "cli/__tests__/**/*.{ts,tsx}",
        "src/__tests__/**/*.{ts,tsx}"
      ],
      "rules": {
        "no-restricted-syntax": [
          "error",
          {
            "selector": "AssignmentExpression[left.object.name=/^(global|window|globalThis)$/][left.property.name='fetch']",
            "message": "Do not mock global.fetch directly. Use MSW handler overrides via `server.use(http.X(...))` instead. See src/test/msw/handlers/*."
          },
          {
            "selector": "CallExpression[callee.object.name='vi'][callee.property.name='mock'][arguments.0.value='axios']",
            "message": "Do not mock axios at the module level. Use MSW handler overrides via `server.use(http.X(...))` instead."
          }
        ]
      }
    }
  ]
}
```

Test the rule:

```bash
echo "global.fetch = vi.fn();" > /tmp/lint-test.ts
pnpm exec eslint --no-eslintrc --config .eslintrc.json /tmp/lint-test.ts
# Should error on the rule. Then delete /tmp/lint-test.ts.
rm /tmp/lint-test.ts
```

**Step 3: Verify lint passes on the existing codebase**

```bash
pnpm lint 2>&1 | tail -10
```

Expected: clean (because Task 3 already removed all the violations). If anything fails the new rule, it's a Task 3 miss — add it to that task's sweep.

**Step 4: Commit**

```bash
cd ..
git add frontend/.eslintrc.json   # or whichever config file
git commit -m "lint(frontend): ban ad-hoc fetch/axios mocks in tests (use MSW server.use)"
```

---

## Task 5: Document MSW usage in `frontend/src/test/msw/README.md`

A short README so future developers don't reinvent the pattern.

**Files:**

- Create: `frontend/src/test/msw/README.md`

**Step 1: Write the README**

````markdown
# MSW Test Setup

All frontend tests route network calls through MSW. Direct `fetch` / `axios` mocking is banned by ESLint.

## How it works

- `frontend/src/test/setup.ts` calls `server.listen({ onUnhandledRequest: 'error' })` once before any test runs.
- Default handlers live in `frontend/src/test/msw/handlers/<domain>.ts` and cover the happy-path response for every endpoint the frontend calls.
- After each test, `server.resetHandlers()` clears any per-test overrides.
- After the suite, `server.close()` tears down the server.

## Adding a new endpoint

1. Pick the right domain file (`auth.ts`, `documents.ts`, …) or create a new one.
2. Export a handler: `http.GET('/api/v1/your-endpoint', () => HttpResponse.json({ ... }))`.
3. Add the export to that domain's array.
4. The handler is now active in every test.

## Per-test override

```ts
import { http, HttpResponse } from "msw";
import { server } from "@/test/msw/server";

it("handles 500 from the server", async () => {
  server.use(
    http.get("/api/v1/documents", () =>
      HttpResponse.json(
        {
          error: {
            message: "boom",
            status_code: 500,
            type: "internal_error",
            timestamp: new Date().toISOString(),
          },
        },
        { status: 500 },
      ),
    ),
  );

  // … assertions
});
```
````

The override applies for this test only. After it finishes, `afterEach` resets to the default handler set.

## Common mistakes

- **Forgetting `await`** on `request.json()` inside a handler.
- **Mismatched URL** — the handler is `/api/v1/foo` but the code calls `/api/foo`. The error from `onUnhandledRequest: 'error'` will be specific.
- **Stale handler** after a real-API change — if production endpoints change, update the corresponding handler.

## Production note

`frontend/src/test/msw/server.ts` is test-only. Do not import it from any file under `src/components`, `src/services`, etc. — only from `src/test/setup.ts` and from tests that need `server.use(...)` overrides.

````

**Step 2: Commit**

```bash
git add frontend/src/test/msw/README.md
git commit -m "docs(frontend): document MSW test setup and override pattern"
````

---

## Task 6: Final verification

**Step 1: Full suite**

```bash
cd frontend && pnpm test 2>&1 | tail -10
```

Expected: all tests pass, all 124+ files green. **`onUnhandledRequest: 'error'` is now load-bearing** — any new test that hits the network without going through MSW will fail loudly.

**Step 2: Lint**

```bash
pnpm lint 2>&1 | tail -10
```

Expected: clean. The new rules apply.

**Step 3: Type-check**

```bash
pnpm type-check 2>&1 | tail -10
```

Expected: same baseline as `develop`.

**Step 4: No residual ad-hoc network mocks**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-pr3-plan
echo "=== should all be empty ==="
grep -rE "(global|window|globalThis)\\.fetch\\s*=" frontend/src frontend/cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null
grep -rlE "mockResolvedValue.*Response|new Response\\(\\s*JSON|fetchMock" frontend/src frontend/cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null
grep -rE "vi\\.mock\\(['\"]axios['\"]\\)" frontend/src frontend/cli --include='*.test.ts' --include='*.test.tsx' 2>/dev/null
```

All should produce no output.

**Step 5: `src/mocks/server.ts` is gone**

```bash
test ! -f frontend/src/mocks/server.ts && echo "Deleted ✓" || echo "STILL EXISTS — fix"
```

**Step 6: Setup file wires MSW**

```bash
grep -E "server\\.(listen|resetHandlers|close)" frontend/src/test/setup.ts
```

Expected: 3 matches.

---

## Task 7: Open the PR

**Step 1: Push**

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-msw  # adjust to actual worktree path
git push -u origin chore/vitest-msw
```

**Step 2: Open PR**

```bash
gh pr create --base develop --title "chore(frontend): standardize MSW for all test network mocking (PR 3/5)" --body "$(cat <<'EOF'
## Summary

Part 3 of 5 of the Vitest migration ([design](./docs/plans/2026-04-29-vitest-migration-design.md), [PR #3 plan](./docs/plans/2026-04-29-vitest-pr3-msw.md)).

This PR makes MSW the single network mocking surface for tests:

- Wires `server.listen({ onUnhandledRequest: 'error' })` into `src/test/setup.ts` — any unmocked network call fails loudly
- Splits the 526-line `src/mocks/server.ts` monolith into per-domain handlers under `src/test/msw/handlers/` (auth, documents, search, threads, evaluation, projects)
- Sweeps every test that mocked `global.fetch`, `axios`, or constructed fake `Response` objects — replaces with `server.use(...)` overrides where the test needs non-default behavior
- Adds an ESLint rule (`no-restricted-syntax`) that bans `global.fetch =` and `vi.mock('axios')` in test files
- New README at `src/test/msw/README.md` documents the pattern

### Out of scope (next PRs)

- PR #4: Zod-validated test fixtures (replace hand-written fixtures with `defineFixture(schema, data)`)
- PR #5: coverage ratchet to 50/40/45/50

## Test plan

- [ ] CI green: full Vitest suite passes
- [ ] `pnpm lint` clean (the new ESLint rule applies)
- [ ] `pnpm type-check` clean (no regression from baseline)
- [ ] No `global.fetch =` in any test file (verified by grep)
- [ ] No `vi.mock('axios')` in any test file
- [ ] `src/mocks/server.ts` is deleted
- [ ] `src/test/msw/handlers/*` is the only place handlers live
EOF
)"
```

**Step 3: Watch CI**

```bash
gh pr checks --watch
```

---

## Definition of done for PR #3

- [ ] All 7 tasks committed
- [ ] PR opened against `develop`
- [ ] CI green; full Vitest suite passes
- [ ] `frontend/src/mocks/server.ts` deleted
- [ ] `frontend/src/test/msw/server.ts` exists, tests import from there
- [ ] `frontend/src/test/msw/handlers/<domain>.ts` files cover every endpoint hit by tests
- [ ] `frontend/src/test/setup.ts` calls `server.listen({ onUnhandledRequest: 'error' })`
- [ ] No `global.fetch =`, `window.fetch =`, `globalThis.fetch =` in any test file
- [ ] No `vi.mock('axios')` in any test file
- [ ] No `mockResolvedValue(new Response(...))` patterns
- [ ] ESLint rule blocks regressions on all of the above
- [ ] `frontend/src/test/msw/README.md` exists

---

## Follow-up plans

- `docs/plans/<date>-vitest-pr4-zod-fixtures.md` — write after PR #3 merges. Add `defineFixture(schema, data)` helper validating against existing Zod schemas (`src/types/schemas.ts`); convert top 5 fixtures (User, Document, Thread, Message, Project); demonstrate the named-export-and-fail pattern.
- `docs/plans/<date>-vitest-pr5-coverage-ratchet.md` — write after PR #4 merges. Bump `vitest.config.mts` thresholds from 0/0/0/0 to 50/40/45/50 on `services`/`hooks`/`utils`; add tests for any module currently below threshold.

Each follows the same bite-sized template, anchored to the [design doc](./2026-04-29-vitest-migration-design.md).
