# Frontend Test Infrastructure Overhaul

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the frontend test infrastructure — centralize shared utilities, add jest-axe for automated a11y, fill critical coverage gaps, and add coverage thresholds.

**Architecture:** Infrastructure-first approach. Build reusable test utilities in `src/test/`, then systematically fill coverage gaps by impact priority. Co-located `__tests__/` structure preserved.

**Tech Stack:** Jest 29, @testing-library/react 14, jest-axe, @testing-library/user-event 14, MSW v2, Zustand

---

### Task 1: Install jest-axe and type definitions

**Files:**

- Modify: `frontend/package.json`

**Step 1: Install jest-axe**

Run: `cd frontend && npm install --save-dev jest-axe @types/jest-axe`

**Step 2: Verify installation**

Run: `cd frontend && node -e "require('jest-axe')"`
Expected: No error

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add jest-axe for automated accessibility testing"
```

---

### Task 2: Consolidate shared test utilities into `src/test/`

**Files:**

- Create: `frontend/src/test/test-utils.tsx`
- Create: `frontend/src/test/factories.ts`
- Create: `frontend/src/test/a11y.ts`
- Modify: `frontend/src/test/setup.ts` (existing file — merge browser API mocks)
- Modify: `frontend/src/setupTests.ts` (import new setup)
- Modify: `frontend/jest.config.js` (add moduleNameMapper alias)

**Step 1: Create `src/test/test-utils.tsx` — custom render with providers**

```tsx
/**
 * Central test render utility — wraps components with all required providers.
 * Usage: import { render, screen } from '@/test/test-utils';
 */
import React, { ReactElement } from "react";
import { render, RenderOptions } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function AllProviders({ children }: { children: React.ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper"> & { wrapper?: React.ComponentType },
) {
  const Wrapper = options?.wrapper ?? AllProviders;
  return {
    user: userEvent.setup(),
    ...render(ui, { wrapper: Wrapper, ...options }),
  };
}

// Re-export everything from testing-library
export * from "@testing-library/react";
export { customRender as render, createTestQueryClient, AllProviders };
```

**Step 2: Create `src/test/factories.ts` — centralized test data factories**

Migrate and consolidate factories from `src/components/__tests__/testUtils.tsx` and inline test factories:

```ts
/**
 * Centralized test data factories.
 * Usage: import { createMockDocument, createMockMessage } from '@/test/factories';
 */

// ── Documents ──
export function createMockDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: "doc-1",
    name: "Test Document.pdf",
    type: "pdf",
    size: 1024000,
    status: "processed",
    uploadDate: "2025-01-18T10:30:00Z",
    processedDate: "2025-01-18T10:35:00Z",
    metadata: {
      pageCount: 10,
      language: "en",
      extractedText: "Sample document content for testing",
      entities: ["Test", "Document"],
      tags: ["test", "document"],
    },
    ...overrides,
  };
}

// ── Search ──
export function createMockSearchResult(
  overrides: Record<string, unknown> = {},
) {
  return {
    id: "result-1",
    content: "Sample search result content",
    score: 0.95,
    source: "document-1",
    sourceType: "text",
    metadata: { page: 1, chunk: 1, confidence: 0.95 },
    ...overrides,
  };
}

// ── Users ──
export function createMockUser(overrides: Record<string, unknown> = {}) {
  return {
    id: "user-1",
    username: "testuser",
    email: "test@example.com",
    role: "user",
    permissions: ["read", "write"],
    createdAt: "2025-01-01T00:00:00Z",
    lastLogin: "2025-01-18T10:30:00Z",
    ...overrides,
  };
}

// ── Chat Widget ──
export function createMockWidgetMessage(
  overrides: Record<string, unknown> = {},
) {
  return {
    id: `msg-${Date.now()}`,
    role: "user" as const,
    content: "Test message",
    timestamp: new Date("2025-01-18T10:30:00Z"),
    ...overrides,
  };
}

export function createMockContextChip(overrides: Record<string, unknown> = {}) {
  return {
    kind: "documents" as const,
    label: "Documents",
    count: 3,
    active: true,
    icon: "file-text" as const,
    ...overrides,
  };
}

// ── Graph ──
export function createMockGraphData(overrides: Record<string, unknown> = {}) {
  return {
    nodes: [
      {
        id: "node-1",
        label: "Test Node",
        type: "entity",
        properties: { name: "Test Node", type: "Person" },
      },
    ],
    edges: [
      {
        id: "edge-1",
        from: "node-1",
        to: "node-2",
        label: "RELATED_TO",
        weight: 0.8,
      },
    ],
    ...overrides,
  };
}

// ── Evaluation ──
export function createMockEvaluationMetric(
  overrides: Record<string, unknown> = {},
) {
  return {
    name: "answer_relevancy",
    value: 0.85,
    target: 0.7,
    unit: "score",
    status: "good" as const,
    trend: "improving" as const,
    lastUpdated: "2025-01-18T10:30:00Z",
    history: [
      { timestamp: "2025-01-17T10:30:00Z", value: 0.82 },
      { timestamp: "2025-01-18T10:30:00Z", value: 0.85 },
    ],
    ...overrides,
  };
}

// ── API helpers ──
export function createMockApiResponse(data: unknown, status = 200) {
  return { data, status, statusText: "OK", headers: {}, config: {} };
}

export function createMockFile(
  name = "test.pdf",
  type = "application/pdf",
  size = 1024,
) {
  const content = new Array(size).fill("a").join("");
  const file = new File([content], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

// ── Project Chat ──
export function createMockStartChatResponse(
  overrides: Record<string, unknown> = {},
) {
  return {
    thread_id: "thread-1",
    conversation_id: "conv-1",
    document_scope: ["doc-1", "doc-2"],
    ...overrides,
  };
}
```

**Step 3: Create `src/test/a11y.ts` — jest-axe helpers**

```ts
/**
 * Accessibility testing helpers powered by jest-axe.
 * Usage: import { expectNoA11yViolations } from '@/test/a11y';
 */
import { axe, toHaveNoViolations } from "jest-axe";

expect.extend(toHaveNoViolations);

/**
 * Assert a rendered container has no axe accessibility violations.
 * @param container - The DOM container from render()
 * @param options - Optional axe-core run options
 */
export async function expectNoA11yViolations(
  container: HTMLElement,
  options?: Parameters<typeof axe>[1],
) {
  const results = await axe(container, options);
  expect(results).toHaveNoViolations();
}
```

**Step 4: Add `@test` alias to jest.config.js**

Add to `moduleNameMapper`:

```js
'^@test/(.*)$': '<rootDir>/src/test/$1',
```

**Step 5: Run tests to verify nothing broke**

Run: `cd frontend && npx jest --passWithNoTests 2>&1 | tail -5`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add frontend/src/test/ frontend/jest.config.js
git commit -m "refactor(test): centralize shared test utilities, factories, and a11y helpers"
```

---

### Task 3: Add coverage thresholds to jest.config.js

**Files:**

- Modify: `frontend/jest.config.js`

**Step 1: Add coverageThreshold to jest config**

Add to `customJestConfig`:

```js
coverageThreshold: {
  global: {
    statements: 25,
    branches: 20,
    functions: 20,
    lines: 25,
  },
},
collectCoverageFrom: [
  'src/components/**/*.{ts,tsx}',
  'src/hooks/**/*.{ts,tsx}',
  'src/services/**/*.{ts,tsx}',
  'src/store/**/*.{ts,tsx}',
  'src/utils/**/*.{ts,tsx}',
  '!src/**/*.d.ts',
  '!src/**/*.stories.{ts,tsx}',
  '!src/**/index.{ts,tsx}',
  '!src/components/ui/**',
],
```

Note: Start with low thresholds (25%) to establish a ratchet baseline — raise after filling gaps.

**Step 2: Verify coverage runs**

Run: `cd frontend && npx jest --coverage --silent 2>&1 | tail -20`
Expected: Coverage report prints, thresholds pass

**Step 3: Commit**

```bash
git add frontend/jest.config.js
git commit -m "chore(test): add coverage thresholds and collection config"
```

---

### Task 4: Add a11y tests for chat-widget components

**Files:**

- Modify: `frontend/src/components/chat-widget/__tests__/ChatContextBar.test.tsx`
- Modify: `frontend/src/components/chat-widget/__tests__/ChatPanelInput.test.tsx`
- Modify: `frontend/src/components/chat-widget/__tests__/ChatPanel.test.tsx`

**Step 1: Add a11y test to ChatContextBar**

Add to end of existing test file:

```tsx
import { expectNoA11yViolations } from "@/test/a11y";

describe("ChatContextBar a11y", () => {
  it("has no accessibility violations", async () => {
    const { container } = render(
      <ChatContextBar
        chips={mockChips}
        onToggleChip={jest.fn()}
        onToggleAll={jest.fn()}
      />,
    );
    await expectNoA11yViolations(container);
  });
});
```

Repeat pattern for ChatPanelInput and ChatPanel.

**Step 2: Run a11y tests**

Run: `cd frontend && npx jest chat-widget --verbose 2>&1 | tail -30`
Expected: All a11y tests pass (components already have aria-labels)

**Step 3: Commit**

```bash
git add frontend/src/components/chat-widget/__tests__/
git commit -m "test(a11y): add jest-axe accessibility tests for chat-widget components"
```

---

### Task 5: Add tests for untested hooks

Priority hooks with 0% coverage: `useDocuments`, `useProjectChat`, `useChatPersistence`, `useWebSocket`, `useKeyboardShortcuts`

**Files:**

- Create: `frontend/src/hooks/__tests__/useDocuments.test.tsx`
- Create: `frontend/src/hooks/__tests__/useKeyboardShortcuts.test.tsx`

**Step 1: Write useDocuments tests**

Test: initial state, fetch documents, error handling, pagination.
Use `renderHook` with `AllProviders` wrapper.

**Step 2: Write useKeyboardShortcuts tests**

Test: registers shortcuts on mount, fires callbacks, cleans up on unmount.
Use `renderHook` + `fireEvent.keyDown`.

**Step 3: Run hook tests**

Run: `cd frontend && npx jest hooks --verbose 2>&1 | tail -20`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/hooks/__tests__/
git commit -m "test: add tests for useDocuments and useKeyboardShortcuts hooks"
```

---

### Task 6: Add tests for untested store slices

Priority stores with 0% coverage: `citationStore`, `sidebar-store`, `pipelineStore`

**Files:**

- Create: `frontend/src/store/__tests__/citationStore.test.ts`
- Create: `frontend/src/store/__tests__/sidebar-store.test.ts`

**Step 1: Write citationStore tests**

Test: initial state, add/remove citations, citation lookup, clear state.
Use `act()` for state mutations.

**Step 2: Write sidebar-store tests**

Test: toggle sidebar, persist collapsed state, responsive behavior.

**Step 3: Run store tests**

Run: `cd frontend && npx jest store --verbose 2>&1 | tail -20`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/store/__tests__/
git commit -m "test: add tests for citationStore and sidebar-store"
```

---

### Task 7: Add tests for high-impact untested components

Priority components: `DocumentLibrary`, `DocumentTable`, `ErrorBoundary` improvements

**Files:**

- Create: `frontend/src/components/documents/__tests__/DocumentLibrary.test.tsx`
- Create: `frontend/src/components/documents/__tests__/DocumentTable.test.tsx`

**Step 1: Write DocumentLibrary tests**

Test: renders document list, empty state, loading state, search/filter, upload trigger.
Use custom render from `@/test/test-utils`.

**Step 2: Write DocumentTable tests**

Test: renders rows, column sorting, row selection, pagination, status badges.

**Step 3: Run component tests**

Run: `cd frontend && npx jest documents --verbose 2>&1 | tail -20`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/documents/__tests__/
git commit -m "test: add tests for DocumentLibrary and DocumentTable components"
```

---

### Task 8: Add a11y tests for high-traffic components

**Files:**

- Modify: `frontend/src/components/research/__tests__/DraftGenerator.accessibility.test.tsx` (extend)
- Create: `frontend/src/components/search/__tests__/SearchInterface.a11y.test.tsx`
- Create: `frontend/src/components/layout/__tests__/Sidebar.a11y.test.tsx`

**Step 1: Add a11y test for SearchInterface**

```tsx
import { render } from "@/test/test-utils";
import { expectNoA11yViolations } from "@/test/a11y";
import SearchInterface from "../SearchInterface";

describe("SearchInterface a11y", () => {
  it("has no accessibility violations", async () => {
    const { container } = render(<SearchInterface />);
    await expectNoA11yViolations(container);
  });
});
```

**Step 2: Add a11y test for Sidebar**

Same pattern — render with providers, run axe, assert no violations.

**Step 3: Run a11y tests**

Run: `cd frontend && npx jest a11y --verbose 2>&1 | tail -20`
Expected: PASS (fix any violations found)

**Step 4: Commit**

```bash
git add frontend/src/components/search/__tests__/ frontend/src/components/layout/__tests__/
git commit -m "test(a11y): add accessibility tests for SearchInterface and Sidebar"
```

---

### Task 9: Migrate existing tests to use shared utilities

**Files:**

- Modify: 3-5 existing test files to use `@/test/test-utils` and `@/test/factories`

**Step 1: Migrate representative tests**

Update imports in these files to use centralized utilities:

- `ChatContextBar.test.tsx` → use `createMockContextChip` from factories
- `useProjectChatWidget.test.tsx` → use factories for mock data
- `projectChatService.test.ts` → use `createMockStartChatResponse`

Replace:

```tsx
import { render, screen } from "@testing-library/react";
```

With:

```tsx
import { render, screen } from "@/test/test-utils";
```

**Step 2: Run all tests to verify migration**

Run: `cd frontend && npx jest --verbose 2>&1 | tail -30`
Expected: All tests pass

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "refactor(test): migrate tests to shared utilities and factories"
```

---

### Task 10: Run full test suite and raise coverage thresholds

**Step 1: Run full coverage report**

Run: `cd frontend && npx jest --coverage 2>&1 | tail -40`

**Step 2: Review coverage numbers and raise thresholds**

Based on the coverage report, raise the thresholds in `jest.config.js` to match current levels (ratchet up — never allow regression).

**Step 3: Final verification**

Run: `cd frontend && npm run validate`
Expected: lint + type-check + test all pass

**Step 4: Commit**

```bash
git add frontend/jest.config.js
git commit -m "chore(test): raise coverage thresholds to match current levels"
```

---

## Summary

| Task | What                   | Impact                          |
| ---- | ---------------------- | ------------------------------- |
| 1    | Install jest-axe       | Enables automated a11y          |
| 2    | Centralize test utils  | DRY, consistent patterns        |
| 3    | Coverage thresholds    | Prevent regression              |
| 4    | Chat-widget a11y tests | Validate new feature            |
| 5    | Hook tests             | ~8% → ~30% hook coverage        |
| 6    | Store tests            | Fill store gaps                 |
| 7    | Component tests        | Fill critical component gaps    |
| 8    | Component a11y tests   | Automated a11y for high-traffic |
| 9    | Migrate existing tests | Consistency                     |
| 10   | Raise thresholds       | Lock in gains                   |
