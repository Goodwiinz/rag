# Vitest Migration — PR #4: Zod-Validated Test Fixtures

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hand-written test factories (`createMockDocument`, etc.) with Zod-validated fixtures via a `defineFixture(schema, data)` helper. If the runtime schema in `frontend/src/types/schemas.ts` ever drifts from a fixture, the test suite breaks at fixture import time — not silently in production.

**Architecture:** Add `frontend/src/test/fixtures/defineFixture.ts` that calls `schema.safeParse` at module load and throws on failure. Convert the top 5 entity fixtures (User, Document, Thread, Message, Project) to use it. Sweep existing `createMock*` callers and the MSW handlers (split in PR #3) to source from the new fixtures. Delete the now-redundant hand-written factories module once all callers migrate.

**Tech Stack:** Zod 3.22 (already installed), Vitest 2.1, TypeScript 5.4, pnpm.

**Source design:** [docs/plans/2026-04-29-vitest-migration-design.md](./2026-04-29-vitest-migration-design.md)

**Predecessor:** PR #446 (PR #3: MSW standardization) must merge first. This plan assumes:

- `frontend/src/test/msw/handlers/<domain>.ts` exists
- `pnpm test` (Vitest) is fully green on `develop`
- `frontend/src/test/factories.ts` is the only remaining hand-written-factory surface

**Branch:** `chore/vitest-fixtures` off `develop`

---

## Pre-flight

```bash
git checkout develop && git pull && git checkout -b chore/vitest-fixtures
cd frontend && pnpm install --frozen-lockfile

# PR #3 must be merged
test -d src/test/msw/handlers || (echo "PR #3 not merged yet; STOP" && exit 1)

# Suite must be green
pnpm test 2>&1 | tail -5

# Schemas inventory (today: 23 schemas in src/types/schemas.ts)
grep -cE "^export const [A-Z][a-zA-Z]*Schema" src/types/schemas.ts
```

If anything fails the baseline, stop.

---

## Task 1: Add `defineFixture` helper

The helper validates fixture data against a Zod schema at module-load time. Bad fixtures fail loudly with a precise error pointing at the field that drifted.

**Files:**

- Create: `frontend/src/test/fixtures/defineFixture.ts`
- Create: `frontend/src/test/fixtures/__tests__/defineFixture.test.ts`

**Step 1: Write the helper**

```ts
// frontend/src/test/fixtures/defineFixture.ts
import type { ZodTypeAny, z } from "zod";

/**
 * Validates fixture data against a runtime Zod schema at module load.
 *
 * If the schema drifts (e.g. a required field is renamed in
 * `src/types/schemas.ts`), the import that uses this fixture throws,
 * and the first test importing it fails with a precise error
 * pointing at the offending field. No silent drift.
 *
 * Usage:
 *   const userFixture = defineFixture(UserSchema, { id: 'u-1', email: 'a@b.com' });
 */
export function defineFixture<S extends ZodTypeAny>(
  schema: S,
  data: z.input<S>,
): z.output<S> {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new Error(
      `Test fixture failed schema validation:\n${result.error.message}`,
    );
  }
  return result.data;
}

/**
 * Variant that returns a factory; useful when each test wants its own
 * mutated copy without invalidating the schema check.
 *
 * Usage:
 *   const buildUser = defineFixtureFactory(UserSchema, { id: 'u-1' });
 *   const user = buildUser({ email: 'override@test.com' });
 */
export function defineFixtureFactory<S extends ZodTypeAny>(
  schema: S,
  base: z.input<S>,
) {
  // Validate the base once at module load.
  defineFixture(schema, base);
  return (overrides: Partial<z.input<S>> = {}): z.output<S> => {
    const merged = { ...base, ...overrides } as z.input<S>;
    return defineFixture(schema, merged);
  };
}
```

**Step 2: Write tests**

```ts
// frontend/src/test/fixtures/__tests__/defineFixture.test.ts
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { defineFixture, defineFixtureFactory } from "../defineFixture";

const TinyUser = z.object({
  id: z.string(),
  email: z.string().email(),
  age: z.number().int().nonnegative().optional(),
});

describe("defineFixture", () => {
  it("returns the parsed data when input is valid", () => {
    const fixture = defineFixture(TinyUser, { id: "u-1", email: "a@b.com" });
    expect(fixture.id).toBe("u-1");
  });

  it("throws with a useful message on invalid input", () => {
    expect(() =>
      defineFixture(TinyUser, { id: "u-1", email: "not-an-email" }),
    ).toThrow(/email/i);
  });

  it("throws when a required field is missing", () => {
    expect(() =>
      // @ts-expect-error — testing runtime guard
      defineFixture(TinyUser, { id: "u-1" }),
    ).toThrow(/email/i);
  });
});

describe("defineFixtureFactory", () => {
  it("validates the base fixture at definition time", () => {
    expect(() =>
      // @ts-expect-error — testing runtime guard
      defineFixtureFactory(TinyUser, { id: "u-1" }),
    ).toThrow(/email/i);
  });

  it("returns a function that merges overrides and validates", () => {
    const buildUser = defineFixtureFactory(TinyUser, {
      id: "u-1",
      email: "a@b.com",
    });
    const user = buildUser({ age: 30 });
    expect(user.age).toBe(30);
  });

  it("throws when overrides break the schema", () => {
    const buildUser = defineFixtureFactory(TinyUser, {
      id: "u-1",
      email: "a@b.com",
    });
    expect(() => buildUser({ email: "bad" })).toThrow(/email/i);
  });
});
```

**Step 3: Run**

```bash
cd frontend && pnpm test src/test/fixtures/__tests__/defineFixture.test.ts 2>&1 | tail -10
```

Expected: 7 passed.

**Step 4: Commit**

```bash
cd ..
git add frontend/src/test/fixtures
git commit -m "test(frontend): add defineFixture helper for Zod-validated test data"
```

---

## Task 2: Convert top 5 entity fixtures

Pick the 5 entities used most across tests. Survey first to confirm:

```bash
cd frontend
grep -rln "createMockUser\\|createMockDocument\\|createMockThread\\|createMockMessage\\|createMockProject" src --include='*.test.ts' --include='*.test.tsx' --include='*.ts' 2>/dev/null | sort -u
```

The current snapshot (today, 2026-05-01): 5 caller files including `src/mocks/server.ts` and `src/test/factories.ts`. Verify this matches what you find.

### Step 1: Confirm the 5 schemas exist

```bash
grep -E "^export const (UserSchema|DocumentSchema|ThreadSchema|MessageSchema|ProjectSchema)\\b" src/types/schemas.ts
```

Expected: at least `UserSchema` and `DocumentSchema` are present today. If `ThreadSchema`, `MessageSchema`, or `ProjectSchema` is missing, **stop and ask** — adding new schemas is out of PR #4 scope. Use whichever 5 schemas are actually exported.

### Step 2: Create per-entity fixture files

One file per entity. Pattern (User as the example):

```ts
// frontend/src/test/fixtures/user.ts
import { UserSchema } from "@/types/schemas";
import { defineFixture, defineFixtureFactory } from "./defineFixture";

/**
 * Default user fixture. Use directly when a test only needs ONE user
 * with default values:
 *
 *   import { userFixture } from '@/test/fixtures/user';
 *
 * If a test needs a customised user, use buildUser() instead.
 */
export const userFixture = defineFixture(UserSchema, {
  id: "u-1",
  email: "demo@example.com",
  // … all required fields per UserSchema
});

export const buildUser = defineFixtureFactory(UserSchema, {
  id: "u-1",
  email: "demo@example.com",
  // …
});
```

Repeat for each of the 5 entities. **Do not invent fields** — copy from `createMockUser`, `createMockDocument`, etc., in the existing `src/test/factories.ts`. The Zod schema is the source of truth; if the existing factory has fields the schema doesn't, drop them. If it lacks required fields, add them with the schema's expected shape.

If `defineFixture` throws when you create the fixture, that's the **point** — fix the data to match the runtime schema before continuing.

### Step 3: Aggregate

```ts
// frontend/src/test/fixtures/index.ts
export * from "./defineFixture";
export * from "./user";
export * from "./document";
export * from "./thread";
export * from "./message";
export * from "./project";
```

### Step 4: Verify all fixtures load

```bash
pnpm exec vitest run src/test/fixtures 2>&1 | tail -15
```

Expected: existing `defineFixture.test.ts` passes, and just _importing_ the fixture files causes their `defineFixture` calls to run; if any throws, the test runner reports it. No "no tests in file" warnings — the imports themselves are the smoke test.

If you want an explicit assertion file, add:

```ts
// frontend/src/test/fixtures/__tests__/fixtures.smoke.test.ts
import { describe, expect, it } from "vitest";
import {
  userFixture,
  documentFixture,
  threadFixture,
  messageFixture,
  projectFixture,
} from "../index";

describe("all fixtures load cleanly under their Zod schemas", () => {
  it("user", () => expect(userFixture.id).toBeDefined());
  it("document", () => expect(documentFixture.id).toBeDefined());
  it("thread", () => expect(threadFixture.id).toBeDefined());
  it("message", () => expect(messageFixture.id).toBeDefined());
  it("project", () => expect(projectFixture.id).toBeDefined());
});
```

### Step 5: Commit

```bash
cd ..
git add frontend/src/test/fixtures
git commit -m "test(frontend): add Zod-validated fixtures for User, Document, Thread, Message, Project"
```

---

## Task 3: Sweep callers — replace `createMock*` with fixtures

### Step 1: Inventory call sites

```bash
cd frontend
grep -rn "createMockUser\\|createMockDocument\\|createMockThread\\|createMockMessage\\|createMockProject" src --include='*.test.ts' --include='*.test.tsx' --include='*.ts' 2>/dev/null
```

### Step 2: Per-file conversion

For each call site:

- `createMockDocument()` (no args) → `documentFixture`
- `createMockDocument({ name: 'foo.pdf' })` (with overrides) → `buildDocument({ name: 'foo.pdf' })`
- `createMockUser({ id: 'u-99', email: 'admin@x.com' })` → `buildUser({ id: 'u-99', email: 'admin@x.com' })`

If the override's field is invalid per the Zod schema, the fixture builder throws — fix the test data, not the schema.

For MSW handlers (`src/test/msw/handlers/<domain>.ts`), replace inline `createMockDocument()` with the imported fixture:

```ts
// frontend/src/test/msw/handlers/documents.ts
import { http, HttpResponse } from "msw";
import { documentFixture, buildDocument } from "@/test/fixtures";

export const documentsHandlers = [
  http.get("/api/v1/documents", () =>
    HttpResponse.json({
      items: [
        documentFixture,
        buildDocument({ id: "doc-2", name: "Other.pdf" }),
      ],
      page: 1,
      // …
    }),
  ),
];
```

Commit per logical batch (3–5 files per commit):

```bash
cd ..
git add frontend/src/services/__tests__/projectChatService.test.ts frontend/src/store/__tests__/projectChatStore.test.ts
git commit -m "test(frontend): use Zod-validated fixtures in projectChat tests"
```

Repeat for every caller until none remain.

### Step 3: Verify no regressions

```bash
cd frontend && pnpm test 2>&1 | tail -10
```

Expected: full suite still green.

---

## Task 4: Delete `frontend/src/test/factories.ts`

Now that all callers source from the new fixtures, the hand-written module is dead.

**Step 1: Confirm zero callers remain**

```bash
cd frontend
grep -rn "from ['\"]@/test/factories['\"]\\|from ['\"]\\.\\./test/factories['\"]\\|from ['\"]\\.\\./\\.\\./test/factories['\"]" src --include='*.ts' --include='*.tsx' 2>/dev/null
grep -rn "createMock(User|Document|Thread|Message|Project)" src --include='*.ts' --include='*.tsx' 2>/dev/null
```

Both must be empty.

**Step 2: Delete**

```bash
git rm src/test/factories.ts
```

**Step 3: Run suite**

```bash
pnpm test 2>&1 | tail -5
```

Expected: green.

**Step 4: Commit**

```bash
cd ..
git commit -m "test(frontend): delete hand-written factories module (replaced by Zod fixtures)"
```

If there are leftover `createMock*` helpers in `factories.ts` that aren't User/Document/Thread/Message/Project, deal with them in one of two ways:

- If they're used by tests — port them too, even though they're not in the "top 5". Add a fixture file per entity, or extend an existing one.
- If they're unused — `git rm` them first (the previous step's grep would have caught usage).

---

## Task 5: Add ESLint rule banning `createMock*` regressions

Prevents future PRs from reintroducing hand-written factories.

**Files:**

- Modify: `frontend/.eslintrc.json` (or whichever config is in use after PR #3)

**Step 1: Add to existing test-file `overrides`**

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
            "selector": "CallExpression[callee.name=/^createMock(User|Document|Thread|Message|Project)$/]",
            "message": "Hand-written factories are deprecated. Import from '@/test/fixtures' (e.g. userFixture, buildUser) — these are Zod-validated against src/types/schemas.ts and will fail at import time if the schema drifts."
          }
        ]
      }
    }
  ]
}
```

(Merge with the rules added in PR #3's Task 4 — don't replace them.)

**Step 2: Verify**

```bash
cd frontend && pnpm lint 2>&1 | tail -10
```

Expected: clean.

**Step 3: Commit**

```bash
cd ..
git add frontend/.eslintrc.json
git commit -m "lint(frontend): ban createMock* helpers in tests (use @/test/fixtures)"
```

---

## Task 6: Document the pattern

**Files:**

- Create: `frontend/src/test/fixtures/README.md`
- Modify: `frontend/src/test/msw/README.md` (cross-link)

**Step 1: Write the README**

````markdown
# Test Fixtures

Zod-validated test data. The Zod schemas in `src/types/schemas.ts` are the runtime contract with the backend — fixtures must match them. If they drift, the test suite breaks at import time, not in CI three days later.

## Default vs builder

Each entity exports two things:

- **`<entity>Fixture`** — a frozen default. Import this when one default copy is enough.
- **`build<Entity>(overrides)`** — a factory. Import this when each test needs a different shape.

```ts
import { userFixture, buildUser } from '@/test/fixtures';

it('renders the default user', () => {
  render(<UserCard user={userFixture} />);
});

it('renders an admin', () => {
  const admin = buildUser({ id: 'u-99', email: 'admin@x.com' });
  render(<UserCard user={admin} />);
});
```
````

## Adding a new fixture

1. Confirm the entity has a Zod schema in `src/types/schemas.ts`.
2. Create `src/test/fixtures/<entity>.ts`:

   ```ts
   import { FooSchema } from "@/types/schemas";
   import { defineFixture, defineFixtureFactory } from "./defineFixture";

   export const fooFixture = defineFixture(FooSchema, {
     /* defaults */
   });
   export const buildFoo = defineFixtureFactory(FooSchema, {
     /* defaults */
   });
   ```

3. Re-export from `index.ts`.
4. If `defineFixture` throws when you load the file: the schema doesn't match your defaults — fix the data, not the schema.

## Why not just `as const` literals?

A typed literal (e.g. `const u: User = { … }`) only catches drift at compile time. Production code calling the same backend would still break at runtime. Zod parsing inside `defineFixture` mirrors the _runtime_ validation production code does, so a fixture that passes is genuinely a valid backend response shape.

````

**Step 2: Cross-link from MSW README**

In `src/test/msw/README.md`, add:

```markdown
## Test data

Handlers should source response data from `@/test/fixtures` (Zod-validated). Do not inline ad-hoc objects unless the test explicitly needs malformed data to test error paths.
````

**Step 3: Commit**

```bash
git add frontend/src/test/fixtures/README.md frontend/src/test/msw/README.md
git commit -m "docs(frontend): document fixture pattern and cross-link from MSW README"
```

---

## Task 7: Final verification

```bash
cd frontend
pnpm test 2>&1 | tail -10        # green
pnpm lint 2>&1 | tail -10        # clean (with new rule)
pnpm type-check 2>&1 | tail -10  # baseline
```

Verify cleanups:

```bash
test ! -f src/test/factories.ts && echo "factories deleted ✓"
ls src/test/fixtures/ | sort
grep -rn "createMock(User|Document|Thread|Message|Project)" src --include='*.ts' --include='*.tsx' 2>/dev/null   # empty
```

---

## Task 8: Open the PR

```bash
cd /Users/goodwiinz/development/RAG_system/.worktrees/vitest-fixtures   # adjust to actual worktree
git push -u origin chore/vitest-fixtures
gh pr create --base develop --title "chore(frontend): Zod-validated test fixtures (PR 4/5)" --body "$(cat <<'EOF'
## Summary

Part 4 of 5 of the Vitest migration ([design](./docs/plans/2026-04-29-vitest-migration-design.md), [PR #4 plan](./docs/plans/2026-04-29-vitest-pr4-zod-fixtures.md)).

Replaces hand-written test factories with **Zod-validated fixtures**. Schemas in `src/types/schemas.ts` are the runtime contract with the backend; fixtures now share that contract. If a schema field renames or a type tightens, the fixture import throws — schema drift is caught at the first test that loads the fixture, not silently in production.

### What changes

- New helper `frontend/src/test/fixtures/defineFixture.ts` validates fixture data via `schema.safeParse` at module load
- 5 entity fixtures: User, Document, Thread, Message, Project — each with both a frozen default and a `build*(overrides)` factory
- All `createMock*` callers swept to use the new fixtures (test files + MSW handlers)
- `frontend/src/test/factories.ts` (hand-written) deleted
- ESLint rule blocks future `createMock*` regressions
- READMEs at `src/test/fixtures/` and updated `src/test/msw/`

### Why

Compile-time types catch drift at edit time. Runtime parsing catches it at execution time — the same way production code would. Both layers protect against schema drift between frontend and backend.

### Out of scope (next PR)

- PR #5: coverage ratchet to 50/40/45/50

## Test plan

- [ ] CI green: full Vitest suite passes
- [ ] `defineFixture` unit tests pass (7 tests)
- [ ] `pnpm lint` clean
- [ ] `pnpm type-check` clean
- [ ] No `createMock(User|Document|Thread|Message|Project)` references remain
- [ ] `src/test/factories.ts` deleted
- [ ] MSW handlers use `@/test/fixtures` for response data
EOF
)"
```

---

## Definition of done for PR #4

- [ ] All 8 tasks committed
- [ ] PR opened against `develop`
- [ ] CI green; full Vitest suite passes
- [ ] `frontend/src/test/fixtures/defineFixture.ts` exists with both `defineFixture` and `defineFixtureFactory`
- [ ] 5 entity fixtures (User, Document, Thread, Message, Project) under `frontend/src/test/fixtures/`
- [ ] `frontend/src/test/fixtures/index.ts` re-exports all fixtures and the helper
- [ ] `frontend/src/test/factories.ts` is deleted
- [ ] No `createMock(User|Document|Thread|Message|Project)` references in tests
- [ ] MSW handlers (from PR #3) use `@/test/fixtures` for response data
- [ ] ESLint rule blocks regressions
- [ ] README at `frontend/src/test/fixtures/README.md` documents the pattern

---

## Follow-up plan

`docs/plans/<date>-vitest-pr5-coverage-ratchet.md` — write after PR #4 merges. Bump `vitest.config.mts` thresholds from 0/0/0/0 to 50/40/45/50 on `services`/`hooks`/`utils`. Add tests for any module currently below threshold. Tracks (and burns down) any `coverage-debt.md` exception list created along the way.

This is the final plan in the migration arc.
