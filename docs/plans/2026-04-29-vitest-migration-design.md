# Vitest Migration Design

**Date:** 2026-04-29
**Owner:** Abdel
**Scope:** `frontend/` (Next.js 15 app + CLI). Backend pytest is out of scope.

---

## 1. Goal

Replace Jest 30 with **Vitest** as the frontend test runner, and standardize the surrounding stack so tests are faster, less mock-heavy, and tied to runtime types:

- **Runner:** Vitest (Vite-native, fast feedback)
- **Unit/Integration:** `@testing-library/react` + MSW (test user behavior, never implementation)
- **E2E:** Playwright (unchanged, already in `frontend/e2e/`)
- **Schema:** Zod (`src/types/schemas.ts`) used to validate test fixtures at import time

## 2. Why

| Driver             | Today                                                | After                                                                |
| ------------------ | ---------------------------------------------------- | -------------------------------------------------------------------- |
| Speed / DX         | Jest + `next/jest` + ts-jest pipeline; slow watch    | Vite + SWC, native ESM, ~2-4× faster watch                           |
| ESM/Next.js compat | Recurring transformer pain on ESM-only deps          | Vitest resolves via Vite, no babel hop                               |
| Coverage gates     | 7-9% thresholds — effectively no gate                | 50% lines / 40% branches on `services`, `hooks`, `utils`             |
| Network mocking    | Ad-hoc `fetch`/`axios` mocks scattered through tests | Single MSW server in `src/test/msw/`                                 |
| Fixture drift      | Hand-written test data drifts from API types         | `defineFixture(schema, data)` validates against existing Zod schemas |

## 3. Non-goals

- Backend pytest changes
- Playwright config changes (E2E already healthy)
- Snapshot tests — none exist; we won't add them
- Visual regression — separate effort, not blocked by this

## 4. Architecture & Layout

End-state file layout in `frontend/`:

```
frontend/
├── vitest.config.ts           # NEW — single source of truth
├── vitest.workspace.ts        # NEW — splits "unit" (jsdom) and "node" (CLI)
├── src/
│   ├── test/
│   │   ├── setup.ts           # NEW — replaces src/setupTests.ts
│   │   ├── msw/
│   │   │   ├── server.ts      # NEW — setupServer() (test-only)
│   │   │   └── handlers/
│   │   │       ├── auth.ts    # split out of mocks/server.ts
│   │   │       ├── documents.ts
│   │   │       ├── search.ts
│   │   │       ├── threads.ts
│   │   │       └── index.ts   # re-exports as `handlers` array
│   │   └── fixtures/
│   │       ├── defineFixture.ts
│   │       ├── user.ts
│   │       ├── document.ts
│   │       ├── thread.ts
│   │       ├── message.ts
│   │       └── project.ts
│   └── mocks/                 # KEEP existing — used by Storybook/dev only
└── package.json               # vitest, @vitest/coverage-v8, @vitest/ui added; jest/ts-jest/jest-* removed
```

### 4.1 `vitest.config.ts`

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false, // explicit imports, no magic globals
    css: { modules: { classNameStrategy: "non-scoped" } },
    testTimeout: 15_000,
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov", "json-summary"],
      reportsDirectory: "./coverage",
      include: [
        "src/components/**/*.{ts,tsx}",
        "src/hooks/**/*.{ts,tsx}",
        "src/services/**/*.{ts,tsx}",
        "src/store/**/*.{ts,tsx}",
        "src/utils/**/*.{ts,tsx}",
      ],
      exclude: [
        "src/**/*.d.ts",
        "src/**/*.stories.{ts,tsx}",
        "src/**/index.{ts,tsx}",
        "src/components/ui/**",
      ],
      thresholds: {
        lines: 50,
        branches: 40,
        functions: 45,
        statements: 50,
      },
    },
    reporters: process.env.CI
      ? ["default", ["junit", { outputFile: "coverage/junit.xml" }]]
      : ["default"],
  },
});
```

### 4.2 `vitest.workspace.ts`

```ts
import { defineWorkspace } from "vitest/config";

export default defineWorkspace([
  {
    extends: "./vitest.config.ts",
    test: {
      name: "unit",
      environment: "jsdom",
      include: ["src/**/__tests__/**/*.test.{ts,tsx}"],
    },
  },
  {
    extends: "./vitest.config.ts",
    test: {
      name: "cli",
      environment: "node",
      include: ["cli/__tests__/**/*.test.{ts,tsx}"],
    },
  },
]);
```

**Why workspaces:** CLI tests don't need jsdom and break under it (no DOM, real `process` IO). Splitting environments is faster and cleaner than per-file overrides.

### 4.3 `src/test/setup.ts`

Replaces `src/setupTests.ts`. Adds MSW lifecycle on top of existing polyfills.

```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { TextEncoder, TextDecoder } from "util";
import { TransformStream as WebTransformStream } from "node:stream/web";
import { server } from "./msw/server";

Object.assign(global, { TextEncoder, TextDecoder });
if (typeof globalThis.TransformStream === "undefined") {
  (globalThis as any).TransformStream = WebTransformStream;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

**Key change:** `onUnhandledRequest: 'error'` — any test that hits the network without an MSW handler fails loudly. This is the lever that ends ad-hoc fetch mocking.

### 4.4 MSW server split

`src/mocks/server.ts` today is a single 600-line file. It moves to `src/test/msw/handlers/<domain>.ts`, one file per API surface. `src/mocks/` stays for Storybook/MDX preview use only.

### 4.5 Zod-validated fixtures

```ts
// src/test/fixtures/defineFixture.ts
import type { ZodTypeAny, z } from "zod";

export function defineFixture<S extends ZodTypeAny>(
  schema: S,
  data: z.input<S>,
): z.output<S> {
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new Error(
      `Fixture failed schema validation:\n${result.error.message}`,
    );
  }
  return result.data;
}
```

```ts
// src/test/fixtures/document.ts
import { DocumentSchema } from "@/types/schemas";
import { defineFixture } from "./defineFixture";

export const documentFixture = defineFixture(DocumentSchema, {
  id: "doc-1",
  name: "Sample.pdf",
  // … field-by-field, type-checked at compile AND runtime
});
```

If the backend changes `DocumentSchema`, the fixture import throws at the first test that uses it — fast-fail, no silent drift.

## 5. Codemod & Manual-Fixup Plan

### 5.1 Automated rewrite

Run `jscodeshift` with `jest-codemods` (Vitest preset):

```sh
pnpm dlx jest-codemods --parser=tsx --transformer=vitest \
  src/**/__tests__/**/*.{ts,tsx} cli/__tests__/**/*.{ts,tsx}
```

Handles:

- `jest.fn()` → `vi.fn()`, `jest.mock` → `vi.mock`, `jest.spyOn` → `vi.spyOn`
- `import { jest } from '@jest/globals'` → `import { vi } from 'vitest'`
- `beforeEach`/`afterEach`/`describe`/`it`/`expect` — auto-imported (since `globals: false`)

### 5.2 Manual fixup checklist (the ~10-20% the codemod misses)

| Pattern                           | Action                                             |
| --------------------------------- | -------------------------------------------------- |
| `jest.useFakeTimers('modern')`    | `vi.useFakeTimers()` (Vitest defaults to modern)   |
| `jest.requireActual`              | `await vi.importActual(...)`                       |
| `jest.isolateModules`             | `vi.isolateModulesAsync` (async API)               |
| `jest.setTimeout(n)`              | per-test `{ timeout: n }` option                   |
| Manual `__mocks__/` folders       | convert to `vi.mock` factories at top of each file |
| `next/jest` Babel-only test paths | none expected after migration; flag any survivors  |
| `identity-obj-proxy` for CSS      | drop — handled by `css.modules.classNameStrategy`  |

### 5.3 Orphan test sweep

Diagnostics flagged tests with broken imports:

- `cli/__tests__/errors.test.ts` → `../errors` missing
- `cli/__tests__/retry.test.ts` → `../retry` missing
- `cli/__tests__/services/draft.test.ts` → `../../services/draft` missing

For each: locate the renamed source, fix the import; if no source exists, the test is dead — delete with a one-line commit message explaining why.

## 6. CI Integration

Existing workflows: `.github/workflows/fast-ci.yml`, `.github/workflows/test-runner.yml` (self-hosted DO runner, Depot frontend, **pnpm only**).

Changes:

- `pnpm test` script: `vitest run` (was `jest`)
- `pnpm test:watch`: `vitest` (no flag)
- `pnpm test:ui`: `vitest --ui` (developer-only)
- `pnpm test:coverage`: `vitest run --coverage`
- CI runs `pnpm test:coverage --reporter=default --reporter=junit`
- Upload `coverage/junit.xml` (existing artifact path) — Vitest's JUnit reporter matches Jest's schema, no downstream changes
- HTML report path stays `coverage/html-report/` (configure via Vitest `html` reporter `reportsDirectory`)

**Coverage ratchet rollout:** PR #5 raises thresholds in one step. Any module below threshold gets tests added in the same PR (preferred) or is added to a tracked `coverage-debt.md` exception list (max 5 entries, expires in 30 days).

## 7. PR Sequence (Approach A — layered)

| #   | PR                                                                                                             | Diff size  | Reversible?  | Gate                                 |
| --- | -------------------------------------------------------------------------------------------------------------- | ---------- | ------------ | ------------------------------------ |
| 1   | Vitest infra alongside Jest; CI dual-runs both                                                                 | ~10 files  | yes          | Both runners green                   |
| 2   | Codemod sweep + remove Jest deps + orphan-test sweep                                                           | ~150 files | yes (revert) | All 148 tests pass on Vitest only    |
| 3   | MSW handler split + `onUnhandledRequest: 'error'` + ESLint rule banning `global.fetch = vi.fn()` in `*.test.*` | ~30 files  | yes          | Tests pass; no unhandled requests    |
| 4   | `defineFixture` helper + 5 core fixtures (User, Document, Thread, Message, Project) + replace usages           | ~25 files  | yes          | Tests pass; fixture-drift test green |
| 5   | Coverage threshold bump (50/40/45/50) + tests for any module below                                             | ~variable  | yes          | Coverage gate passes                 |

**Branch strategy:** each PR off `develop`, target `develop`. Feature flag not needed — runner swap is build-time, not runtime.

## 8. Risks & Mitigations

| Risk                                                                    | Likelihood | Mitigation                                                                         |
| ----------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------- |
| `next/navigation` / `next/router` mocks behave differently under Vitest | Med        | Centralize in `src/test/setup.ts` once; codemod replaces existing per-file mocks   |
| Some Jest matchers from `jest-extended` not in Vitest                   | Low        | Audit usage in PR #2; replace with native or `@vitest/expect` extensions           |
| MSW `onUnhandledRequest: 'error'` flushes hidden network calls          | High       | Expected — this is the point. Fix or scope the test. PR #3 includes an audit pass. |
| Coverage drop in modules without good tests                             | High       | Tests added in PR #5 alongside the threshold bump; debt list as escape hatch       |
| Self-hosted runner caches Jest deps                                     | Low        | Cache key includes `package.json` hash; PR #2 invalidates automatically            |
| Snapshot tests                                                          | N/A        | None exist                                                                         |

## 9. Success Criteria

- All 148 tests run on Vitest, CI green
- `pnpm test` watch is measurably faster (target: ≥2× on `services/__tests__/**`)
- Zero `global.fetch` / `axios.create` mock patterns left in `*.test.*` files (ESLint enforced)
- Top 5 fixtures Zod-validated; renaming a schema field breaks the fixture import (verified by a deliberate failing-test PR check)
- Coverage gate at 50/40/45/50 on `services`, `hooks`, `utils`
- Jest, ts-jest, jest-junit, jest-html-reporters, identity-obj-proxy removed from `package.json`

## 10. Out-of-band Cleanups (bundle into PR #2)

- Delete `frontend/jest.config.js`, `frontend/src/setupTests.ts`
- Remove `testPathIgnorePatterns` workaround for `App.routing.test.tsx` (port the test or delete it; current state is "Jest can't run it")
- Drop `craco.config.js` if unused post-migration (verify first; it predates Next.js)

---

## Appendix A — Decisions log

| Decision                                   | Why                                                        |
| ------------------------------------------ | ---------------------------------------------------------- |
| `globals: false`                           | Explicit imports beat magic; matches Next.js TS strictness |
| V8 coverage (not istanbul)                 | Faster, no instrumentation pass, native to Vitest          |
| Workspace split (unit + cli)               | CLI tests need node env; per-file overrides are fragile    |
| Keep `src/mocks/` for Storybook            | Don't conflate dev mocks with test mocks                   |
| `onUnhandledRequest: 'error'` from day one | The whole point of MSW standardization                     |
| One PR per layer (not mega-PR)             | Reviewability; clear rollback points                       |
| Codemod over hand-rewrite                  | 148 files; mechanical changes belong to a tool             |
| Zod fixtures only for top 5 entities       | YAGNI; expand once the pattern proves out                  |
