# CLI Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the NOUS CLI safe to interrupt, surface actionable errors, fix the long-standing `clears a missing confirmation thread` test failure, and add `/retry` + draft-restore.

**Architecture:** Three new pure modules (`errors.ts`, `retry.ts`, `services/draft.ts`) plus targeted edits to `stream.ts`, `prompt.ts`, `services/client.ts`, and `repl.ts`. No new dependencies, no backend changes. Detailed in `docs/plans/2026-04-26-cli-polish-design.md`.

**Tech Stack:** TypeScript, Node 20+, Jest (jsdom default but each CLI test pins `@jest-environment node`), `@clack/prompts`, Node `readline`. Run from `frontend/`: `npx tsc --noEmit` for type-check, `npx jest cli/` for tests.

---

## Conventions for every task

- **Run from:** `/Users/goodwiinz/development/RAG_system/frontend`
- **TDD order is non-negotiable:** failing test first, run it, see RED, then minimal code, run again, see GREEN, then commit.
- **One commit per task.** Commit message format: `<type>(cli): <subject>`. Types: `feat`, `fix`, `refactor`, `test`, `docs`.
- **Co-author trailer:** every commit ends with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` (per repo convention).
- **Never use `git add -A` or `git add .`.** Add only the files this task touched.
- **No `--no-verify`, no `--amend`.** Pre-commit hooks must pass.
- **Branch:** `fix/hitl-post-confirm-ux` (current). The design doc was just committed here as `20691b2`.
- **Reference files:** `frontend/cli/repl.ts`, `frontend/cli/stream.ts`, `frontend/cli/prompt.ts`, `frontend/cli/services/{client,promptHistory}.ts`. Read them before editing — the design assumes their current shapes.

---

## Task 1: errors.ts — types + first 3 mappings (network / auth / unknown)

**Files:**

- Create: `frontend/cli/errors.ts`
- Create: `frontend/cli/__tests__/errors.test.ts`

**Step 1: Write the failing test**

```ts
// frontend/cli/__tests__/errors.test.ts
/**
 * @jest-environment node
 */
import { classifyError } from "../errors";

describe("classifyError — network", () => {
  test("Error with code ECONNREFUSED → network, retryable", () => {
    const err = Object.assign(new Error("connect ECONNREFUSED"), {
      code: "ECONNREFUSED",
    });
    const c = classifyError(err);
    expect(c.kind).toBe("network");
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/not reachable/i);
  });

  test('Error message containing "fetch failed" → network', () => {
    const c = classifyError(new Error("fetch failed"));
    expect(c.kind).toBe("network");
    expect(c.retryable).toBe(true);
  });

  test("nested cause with ECONNREFUSED → network", () => {
    const err = new Error("wrapped", {
      cause: { code: "ECONNREFUSED" },
    });
    expect(classifyError(err).kind).toBe("network");
  });
});

describe("classifyError — auth", () => {
  test('"Not logged in" → auth, not retryable', () => {
    const c = classifyError(new Error("Not logged in. Run: ./nous login"));
    expect(c.kind).toBe("auth");
    expect(c.retryable).toBe(false);
    expect(c.hint).toMatch(/login/i);
  });

  test("message containing 401 → auth", () => {
    expect(classifyError("Stream failed: 401").kind).toBe("auth");
  });
});

describe("classifyError — unknown", () => {
  test("null input → unknown, not retryable", () => {
    const c = classifyError(null);
    expect(c.kind).toBe("unknown");
    expect(c.retryable).toBe(false);
  });

  test("Error without message → unknown", () => {
    const c = classifyError(new Error(""));
    expect(c.kind).toBe("unknown");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npx jest cli/__tests__/errors.test.ts`
Expected: FAIL with `Cannot find module '../errors'`.

**Step 3: Write minimal implementation**

```ts
// frontend/cli/errors.ts
export type ErrorKind =
  | "network"
  | "auth"
  | "not_found_thread"
  | "transient_5xx"
  | "idle_timeout"
  | "cancelled"
  | "unknown";

export interface ClassifiedError {
  kind: ErrorKind;
  retryable: boolean;
  userMessage: string;
  hint?: string;
  raw?: unknown;
}

function messageOf(input: unknown): string {
  if (input == null) return "";
  if (typeof input === "string") return input;
  if (input instanceof Error) return input.message ?? "";
  if (typeof input === "object" && "message" in input) {
    const m = (input as { message?: unknown }).message;
    return typeof m === "string" ? m : "";
  }
  return "";
}

function codeOf(input: unknown): string | undefined {
  if (input instanceof Error) {
    const direct = (input as Error & { code?: unknown }).code;
    if (typeof direct === "string") return direct;
    const cause = (input as Error & { cause?: unknown }).cause;
    if (cause && typeof cause === "object" && "code" in cause) {
      const c = (cause as { code?: unknown }).code;
      if (typeof c === "string") return c;
    }
  }
  return undefined;
}

const NETWORK_CODES = new Set(["ECONNREFUSED", "ENOTFOUND", "EAI_AGAIN"]);

export function classifyError(input: unknown): ClassifiedError {
  const msg = messageOf(input);
  const code = codeOf(input);

  if (code && NETWORK_CODES.has(code)) {
    return network(msg, input);
  }
  if (/getaddrinfo|fetch failed/i.test(msg)) {
    return network(msg, input);
  }

  if (/not logged in|401|403|unauthorized/i.test(msg)) {
    return {
      kind: "auth",
      retryable: false,
      userMessage: "Session expired or unauthorized.",
      hint: "Run ./nous login.",
      raw: input,
    };
  }

  return {
    kind: "unknown",
    retryable: false,
    userMessage: msg || "Unknown error.",
    raw: input,
  };
}

function network(_msg: string, raw: unknown): ClassifiedError {
  return {
    kind: "network",
    retryable: true,
    userMessage: "Backend not reachable.",
    hint: "Set NOUS_API_URL or run /settings.",
    raw,
  };
}
```

**Step 4: Run test to verify it passes**

Run: `npx jest cli/__tests__/errors.test.ts`
Expected: PASS, 7 tests.

**Step 5: Commit**

```bash
git add frontend/cli/errors.ts frontend/cli/__tests__/errors.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): add error classifier with network/auth/unknown kinds

First slice of the error classification seam. Pure function, no I/O.
Subsequent commits add not_found_thread / transient_5xx / idle_timeout /
cancelled mappings and wire it into repl.ts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: errors.ts — remaining mappings (not_found_thread, transient_5xx, idle_timeout, cancelled)

**Files:**

- Modify: `frontend/cli/errors.ts`
- Modify: `frontend/cli/__tests__/errors.test.ts`

**Step 1: Add failing tests**

Append to `errors.test.ts`:

```ts
describe("classifyError — not_found_thread", () => {
  test('"Thread not found" → not_found_thread, retryable', () => {
    const c = classifyError(new Error("Thread not found"));
    expect(c.kind).toBe("not_found_thread");
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/expired/i);
  });
});

describe("classifyError — transient_5xx", () => {
  test('"Stream failed: 502" → transient_5xx, retryable', () => {
    expect(classifyError("Stream failed: 502").kind).toBe("transient_5xx");
  });
  test('"Stream failed: 503" → transient_5xx', () => {
    expect(classifyError("Stream failed: 503").kind).toBe("transient_5xx");
  });
  test('generic "timed out" → transient_5xx', () => {
    expect(classifyError(new Error("request timed out")).kind).toBe(
      "transient_5xx",
    );
  });
});

describe("classifyError — idle_timeout", () => {
  test("IDLE_TIMEOUT:90 sentinel → idle_timeout, retryable", () => {
    const c = classifyError("IDLE_TIMEOUT:90");
    expect(c.kind).toBe("idle_timeout");
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/silent at 90s/);
  });
});

describe("classifyError — cancelled", () => {
  test("AbortError → cancelled, not retryable", () => {
    const err = Object.assign(new Error("aborted"), { name: "AbortError" });
    const c = classifyError(err);
    expect(c.kind).toBe("cancelled");
    expect(c.retryable).toBe(false);
  });
});

describe("classifyError — precedence", () => {
  test("IDLE_TIMEOUT does NOT match generic transient_5xx timeout rule", () => {
    expect(classifyError("IDLE_TIMEOUT:30").kind).toBe("idle_timeout");
  });
  test("not_found_thread beats unknown even when message has noise", () => {
    expect(
      classifyError(new Error("Stream failed: Thread not found")).kind,
    ).toBe("not_found_thread");
  });
});
```

**Step 2: Run — expect 8 new failures**

Run: `npx jest cli/__tests__/errors.test.ts`

**Step 3: Extend `classifyError`**

Insert these branches **before** the `auth` branch, in this order: `cancelled`, `idle_timeout`, `not_found_thread`, `transient_5xx`. (Order matters — `idle_timeout` and `not_found_thread` must beat `transient_5xx`'s `timed out` regex; `auth`'s `401` regex must not steal `Stream failed: 502`.)

```ts
// inside classifyError, after the network checks
if (input instanceof Error && input.name === "AbortError") {
  return {
    kind: "cancelled",
    retryable: false,
    userMessage: "Cancelled.",
    raw: input,
  };
}

const idleMatch = msg.match(/^IDLE_TIMEOUT:(\d+)$/);
if (idleMatch) {
  return {
    kind: "idle_timeout",
    retryable: true,
    userMessage: `Agent went silent at ${idleMatch[1]}s.`,
    hint: "Retrying once…",
    raw: input,
  };
}

if (/thread not found/i.test(msg)) {
  return {
    kind: "not_found_thread",
    retryable: true,
    userMessage: "Cached thread expired.",
    hint: "Starting a fresh thread…",
    raw: input,
  };
}

if (/Stream failed: 5\d\d/.test(msg) || /timeout|timed out/i.test(msg)) {
  return {
    kind: "transient_5xx",
    retryable: true,
    userMessage: "Backend hiccup (HTTP 5xx).",
    hint: "Retrying once…",
    raw: input,
  };
}
```

**Step 4: Run — expect all green**

Run: `npx jest cli/__tests__/errors.test.ts`
Expected: PASS, all ~15 tests.

**Step 5: Commit**

```bash
git add frontend/cli/errors.ts frontend/cli/__tests__/errors.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): finish error classifier (5xx, idle, thread, cancelled)

Adds the remaining mappings called out in the design doc. Order is
load-bearing — idle_timeout and not_found_thread must beat transient_5xx
on overlapping messages.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: retry.ts — generic withRetry helper

**Files:**

- Create: `frontend/cli/retry.ts`
- Create: `frontend/cli/__tests__/retry.test.ts`

**Step 1: Write the failing test**

```ts
// frontend/cli/__tests__/retry.test.ts
/**
 * @jest-environment node
 */
import { withRetry } from "../retry";

describe("withRetry", () => {
  test("returns immediately when first attempt succeeds", async () => {
    const fn = jest.fn().mockResolvedValue("ok");
    const out = await withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    expect(out).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test("retries when predicate is true; returns on success", async () => {
    jest.useFakeTimers();
    const fn = jest
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce("ok");
    const promise = withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    // advance backoff (250ms for first retry)
    await jest.advanceTimersByTimeAsync(250);
    const out = await promise;
    expect(out).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test("does NOT retry when predicate returns false", async () => {
    const fn = jest.fn().mockRejectedValue(new Error("nope"));
    await expect(
      withRetry(fn, {
        maxAttempts: 3,
        signal: new AbortController().signal,
        predicate: () => false,
      }),
    ).rejects.toThrow("nope");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test("throws AbortError when signal is already aborted", async () => {
    const ac = new AbortController();
    ac.abort();
    const fn = jest.fn();
    await expect(
      withRetry(fn, {
        maxAttempts: 3,
        signal: ac.signal,
        predicate: () => true,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fn).not.toHaveBeenCalled();
  });

  test("stops retrying after maxAttempts and rethrows last error", async () => {
    jest.useFakeTimers();
    const err = new Error("persistent");
    const fn = jest.fn().mockRejectedValue(err);
    const promise = withRetry(fn, {
      maxAttempts: 2,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    await jest.advanceTimersByTimeAsync(250);
    await expect(promise).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });
});
```

**Step 2: Run — expect FAIL (`Cannot find module '../retry'`)**

Run: `npx jest cli/__tests__/retry.test.ts`

**Step 3: Implement**

```ts
// frontend/cli/retry.ts
export interface RetryOptions {
  maxAttempts: number;
  signal: AbortSignal;
  predicate: (err: unknown) => boolean;
}

const BACKOFF_MS = [250, 750];

export async function withRetry<T>(
  fn: (attempt: number) => Promise<T>,
  opts: RetryOptions,
): Promise<T> {
  if (opts.signal.aborted) throw abortError();

  let lastErr: unknown;
  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastErr = err;
      if (attempt >= opts.maxAttempts || !opts.predicate(err)) throw err;
      const delay = BACKOFF_MS[Math.min(attempt - 1, BACKOFF_MS.length - 1)];
      await sleep(delay, opts.signal);
    }
  }
  throw lastErr;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(abortError());
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function abortError(): Error {
  const e = new Error("aborted");
  e.name = "AbortError";
  return e;
}
```

**Step 4: Run — expect PASS**

Run: `npx jest cli/__tests__/retry.test.ts`
Expected: 5 PASS.

**Step 5: Commit**

```bash
git add frontend/cli/retry.ts frontend/cli/__tests__/retry.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): add withRetry helper with fixed backoff

Generic retry-with-predicate. Backoff is fixed (250ms, 750ms). Caller
owns predicate so this stays decoupled from the error classifier.
AbortSignal short-circuits before and during sleep.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: services/draft.ts — load/save/clear at ~/.nous/draft.txt

**Files:**

- Create: `frontend/cli/services/draft.ts`
- Create: `frontend/cli/__tests__/services/draft.test.ts`

**Step 1: Write the failing test**

```ts
// frontend/cli/__tests__/services/draft.test.ts
/**
 * @jest-environment node
 */
import { mkdtempSync, rmSync, writeFileSync } from "fs";
import * as os from "os";
import * as path from "path";

describe("draft store", () => {
  let tmp: string;
  let store: typeof import("../../services/draft");

  beforeEach(() => {
    tmp = mkdtempSync(path.join(os.tmpdir(), "nous-draft-"));
    process.env.NOUS_CONFIG_DIR = tmp;
    jest.resetModules();
    store = require("../../services/draft");
  });

  afterEach(() => {
    delete process.env.NOUS_CONFIG_DIR;
    rmSync(tmp, { recursive: true, force: true });
  });

  test("readDraft returns empty string when missing", () => {
    expect(store.readDraft()).toBe("");
  });

  test("writeDraft + readDraft round-trips multiline content", () => {
    store.writeDraft("hello\nworld");
    expect(store.readDraft()).toBe("hello\nworld");
  });

  test("writeDraft with empty string clears the file", () => {
    store.writeDraft("seed");
    store.writeDraft("");
    expect(store.readDraft()).toBe("");
  });

  test("clearDraft empties the file", () => {
    store.writeDraft("something");
    store.clearDraft();
    expect(store.readDraft()).toBe("");
  });

  test("readDraft survives a malformed (non-utf8) file gracefully", () => {
    writeFileSync(path.join(tmp, "draft.txt"), Buffer.from([0xff, 0xfe]));
    // Should not throw; content may be replacement chars but type is string
    expect(typeof store.readDraft()).toBe("string");
  });
});
```

**Step 2: Run — FAIL** (`Cannot find module '../../services/draft'`)

**Step 3: Implement**

```ts
// frontend/cli/services/draft.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import * as os from "os";
import * as path from "path";

const FILE = "draft.txt";

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), ".nous");
}

function filePath(): string {
  return path.join(configDir(), FILE);
}

function ensureDir(): void {
  const dir = configDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

export function readDraft(): string {
  try {
    if (!existsSync(filePath())) return "";
    return readFileSync(filePath(), "utf-8");
  } catch {
    return "";
  }
}

export function writeDraft(text: string): void {
  ensureDir();
  writeFileSync(filePath(), text, "utf-8");
}

export function clearDraft(): void {
  writeDraft("");
}
```

**Step 4: Run — PASS** (5 tests).

**Step 5: Commit**

```bash
git add frontend/cli/services/draft.ts frontend/cli/__tests__/services/draft.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): add draft persistence at ~/.nous/draft.txt

Mirrors promptHistory.ts. Used by upcoming prompt.ts integration to
restore in-progress input across Ctrl-C / relaunch.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: services/client.ts — embed URL in fetch errors

**Files:**

- Modify: `frontend/cli/services/client.ts`
- Modify: `frontend/cli/__tests__/services/client.test.ts` (add new test)
- Modify: `frontend/cli/errors.ts` (use embedded URL in network hint)
- Modify: `frontend/cli/__tests__/errors.test.ts` (cover URL-embedded hint)

**Step 1: Add failing test for URL-embedding**

Append to `errors.test.ts`:

```ts
test("network classification embeds URL from error message in hint", () => {
  const err = Object.assign(
    new Error("fetch failed at http://localhost:8000/api/v1/agent/stream"),
    { code: "ECONNREFUSED" },
  );
  const c = classifyError(err);
  expect(c.kind).toBe("network");
  expect(c.userMessage).toContain("http://localhost:8000");
});
```

**Step 2: Run — FAIL**

**Step 3: Implement**

In `errors.ts`, replace the `network()` helper:

```ts
function network(msg: string, raw: unknown): ClassifiedError {
  const urlMatch = msg.match(/(https?:\/\/[^\s)]+)/);
  const url = urlMatch ? urlMatch[1] : null;
  return {
    kind: "network",
    retryable: true,
    userMessage: url
      ? `Backend not reachable at ${url}.`
      : "Backend not reachable.",
    hint: "Set NOUS_API_URL or run /settings.",
    raw,
  };
}
```

Then in `services/client.ts`, add a `safeFetch` helper that wraps any fetch error with the URL:

```ts
export async function safeFetch(
  url: string,
  init?: RequestInit,
  fetchFn: typeof fetch = fetch,
): Promise<Response> {
  try {
    return await fetchFn(url, init);
  } catch (err) {
    const orig = err instanceof Error ? err.message : String(err);
    const wrapped = new Error(`fetch failed at ${url}: ${orig}`);
    if (err instanceof Error) {
      (wrapped as Error & { code?: string }).code = (
        err as Error & { code?: string }
      ).code;
      (wrapped as Error & { cause?: unknown }).cause = err;
    }
    throw wrapped;
  }
}
```

**Note:** Do NOT change `stream.ts` to use `safeFetch` in this task — keep the change scoped. Stream wiring happens in Task 7.

**Step 4: Run errors + client tests**

Run: `npx jest cli/__tests__/errors.test.ts cli/__tests__/services/client.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/cli/errors.ts frontend/cli/__tests__/errors.test.ts \
  frontend/cli/services/client.ts frontend/cli/__tests__/services/client.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): wrap fetch errors with target URL for actionable hints

Adds safeFetch helper that re-raises any fetch failure with the URL
embedded in the message. classifyError(network) extracts the URL into
its userMessage so users see exactly which endpoint is unreachable.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: stream.ts — idle timeout watchdog

**Files:**

- Modify: `frontend/cli/stream.ts`
- Modify: `frontend/cli/__tests__/stream.test.ts`

**Step 1: Write the failing test**

Append to `stream.test.ts`:

```ts
test("emits IDLE_TIMEOUT sentinel error when no events arrive within idleTimeoutMs", async () => {
  const slowResponse = {
    ok: true,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        // never enqueue anything; stream hangs
        void controller;
      },
    }),
  };
  const mockFetch = jest.fn().mockResolvedValue(slowResponse);

  const events: unknown[] = [];
  for await (const e of streamAgent(
    "hi",
    {},
    { fetchFn: mockFetch as never, idleTimeoutMs: 50 },
  )) {
    events.push(e);
    if ((e as { type: string }).type === "error") break;
  }

  expect(events).toContainEqual({
    type: "error",
    message: expect.stringMatching(/^IDLE_TIMEOUT:0$/),
  });
});
```

**Step 2: Run — FAIL** (no `idleTimeoutMs` option, stream hangs forever).

**Step 3: Implement**

In `stream.ts`:

```ts
export interface StreamOptions {
  fetchFn?: typeof fetch;
  signal?: AbortSignal;
  idleTimeoutMs?: number;
}

const DEFAULT_IDLE_MS = (() => {
  const env = process.env.NOUS_STREAM_IDLE_MS;
  const parsed = env ? Number.parseInt(env, 10) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 90000;
})();
```

Wrap `_parseSseBody` to race each `reader.read()` against an idle timer. Cleanest is a new helper that yields events and a sentinel:

```ts
async function* _withIdleTimeout(
  body: ReadableStream<Uint8Array>,
  idleMs: number,
  onTrace?: (threadId: string) => void,
): AsyncGenerator<StreamEvent> {
  const inner = _parseSseBody(body, onTrace);
  while (true) {
    const next = inner.next();
    let timer: NodeJS.Timeout | null = null;
    const timeout = new Promise<{ done: true; idle: true }>((resolve) => {
      timer = setTimeout(
        () => resolve({ done: true, idle: true } as const),
        idleMs,
      );
    });
    const winner = await Promise.race([next, timeout]);
    if (timer) clearTimeout(timer);
    if ((winner as { idle?: boolean }).idle) {
      yield {
        type: "error",
        message: `IDLE_TIMEOUT:${Math.round(idleMs / 1000)}`,
      };
      try {
        await body.cancel();
      } catch {
        /* best effort */
      }
      return;
    }
    const r = winner as IteratorResult<StreamEvent>;
    if (r.done) return;
    yield r.value;
  }
}
```

Then in both `streamAgent` and `streamConfirm`, replace `yield* _parseSseBody(res.body, persistThreadId);` with:

```ts
const idleMs = options.idleTimeoutMs ?? DEFAULT_IDLE_MS;
yield * _withIdleTimeout(res.body, idleMs, persistThreadId);
```

**Step 4: Run — PASS**

Run: `npx jest cli/__tests__/stream.test.ts`
Expected: all stream tests pass, including the new one.

**Step 5: Commit**

```bash
git add frontend/cli/stream.ts frontend/cli/__tests__/stream.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): add idle-timeout watchdog to SSE streams

Emits IDLE_TIMEOUT:<seconds> sentinel error when no SSE event arrives
within idleTimeoutMs (default 90s, override NOUS_STREAM_IDLE_MS). The
upcoming classifier maps this to ErrorKind.idle_timeout and withRetry
re-runs once.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: prompt.ts — initialValue + draft writes on keypress

**Files:**

- Modify: `frontend/cli/prompt.ts`
- Modify: `frontend/cli/__tests__/prompt.test.ts`

**Step 1: Add failing test**

Append to `prompt.test.ts`:

```ts
import { writeDraft, readDraft, clearDraft } from "../services/draft";
jest.mock("../services/draft");

const mockedWriteDraft = writeDraft as jest.MockedFunction<typeof writeDraft>;
const mockedClearDraft = clearDraft as jest.MockedFunction<typeof clearDraft>;
void readDraft;

describe("readPrompt — non-TTY initialValue passthrough", () => {
  test("passes initialValue to clack text fallback", async () => {
    // Already covered by clack mock in this file; verify the option is forwarded.
    const { readPrompt } = await import("../prompt");
    const prompts = await import("@clack/prompts");
    const textMock = prompts.text as jest.Mock;
    textMock.mockResolvedValueOnce("result");
    await readPrompt({ message: ">", initialValue: "restored" });
    expect(textMock).toHaveBeenCalledWith(
      expect.objectContaining({ initialValue: "restored" }),
    );
  });
});

describe("readPrompt — clears draft on submit (non-TTY)", () => {
  test("clearDraft is called when prompt resolves to a string", async () => {
    const { readPrompt } = await import("../prompt");
    const prompts = await import("@clack/prompts");
    (prompts.text as jest.Mock).mockResolvedValueOnce("hello");
    await readPrompt({ message: ">" });
    expect(mockedClearDraft).toHaveBeenCalled();
  });
});
```

**Step 2: Run — FAIL** (`initialValue` not in `PromptOptions`; `clearDraft` not called).

**Step 3: Implement**

In `prompt.ts`:

```ts
import { clearDraft, writeDraft } from "./services/draft";

export interface PromptOptions {
  message: string;
  completer?: (line: string) => string[];
  initialValue?: string;
}
```

In the non-TTY branch:

```ts
if (!process.stdin.isTTY) {
  const r = await p.text({
    message: opts.message,
    initialValue: opts.initialValue,
  });
  if (p.isCancel(r)) return CANCEL;
  clearDraft();
  return r as string;
}
```

In the TTY branch, after `rl.question(...)`'s success callback, before `appendHistory`:

```ts
rl.question(`${opts.message} `, (answer) => {
  const trimmed = answer.trim();
  if (trimmed) appendHistory(trimmed);
  clearDraft();
  finish(answer);
});
```

Also, **debounced draft writes on each keypress** — wire it inside the TTY branch only, after `createInterface`:

```ts
let draftTimer: NodeJS.Timeout | null = null;
const scheduleDraftWrite = () => {
  if (draftTimer) clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    // rl.line is the current buffer
    writeDraft((rl as unknown as { line: string }).line ?? "");
  }, 300);
};
process.stdin.on("keypress", scheduleDraftWrite);
rl.on("close", () => {
  if (draftTimer) clearTimeout(draftTimer);
  process.stdin.off("keypress", scheduleDraftWrite);
});

// prefill from initialValue
if (opts.initialValue) {
  // readline doesn't accept a default value through createInterface;
  // write it after the question is shown.
  setImmediate(() => {
    rl.write(opts.initialValue ?? "");
  });
}
```

**Step 4: Run — PASS**

Run: `npx jest cli/__tests__/prompt.test.ts`

**Step 5: Commit**

```bash
git add frontend/cli/prompt.ts frontend/cli/__tests__/prompt.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): persist in-progress input as draft, restore via initialValue

Debounced 300ms writeDraft on each readline keypress. clearDraft on
submit. Non-TTY fallback forwards initialValue to clack so existing
test mocks pick it up.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: repl.ts — route all error events through classifier (fixes failing test)

**Files:**

- Modify: `frontend/cli/repl.ts`
- Modify: `frontend/cli/__tests__/repl.test.ts`

This is the load-bearing task — the long-standing pre-existing failure should turn green here.

**Step 1: Verify the existing failing test still fails**

Run: `npx jest cli/__tests__/repl.test.ts -t "clears a missing confirmation thread"`
Expected: FAIL — `mockedSaveConfig` was called 0 times, expected to be called with `{ thread_id: null }`.

**Step 2: Refactor `streamToTerminal`'s error branch**

Open `frontend/cli/repl.ts`. Find the `else if (event.type === 'error')` branch (around line 257). Replace its body with classifier-driven dispatch:

```ts
} else if (event.type === 'error') {
  process.stdout.write('\n');
  const classified = classifyError(event.message);
  if (classified.kind === 'not_found_thread' && !retriedAfterMissingThread) {
    clearCachedThreadId();
    retriedAfterMissingThread = true;
    retryFreshThread = true;
    p.log.warn(`${classified.userMessage} ${classified.hint ?? ''}`.trim());
    break;
  }
  p.log.error(classified.userMessage);
  if (classified.hint) p.log.message(`  ${classified.hint}`);
  return;
}
```

Note: the `!inConfirmFlow` guard is **gone**. That guard is what produced the failing test.

Add the import at the top:

```ts
import { classifyError } from "./errors";
```

**Step 3: Run the previously-failing test**

Run: `npx jest cli/__tests__/repl.test.ts -t "clears a missing confirmation thread"`
Expected: **PASS.**

If it still fails, the design is wrong — STOP and report. Do not patch around it.

**Step 4: Run the full repl + cli suite**

Run: `npx jest cli/`
Expected: previously-pre-existing failure now green. No new failures introduced.

**Step 5: Commit**

```bash
git add frontend/cli/repl.ts
git commit -m "$(cat <<'EOF'
fix(cli): route all SSE errors through classifier

Removes the !inConfirmFlow guard that caused the long-standing
"clears a missing confirmation thread" test failure. Both first-turn
and confirm-flow branches now share one code path:
  classifyError(message) → not_found_thread? clear cache + retry, else
  surface userMessage/hint and return.

Test: cli/__tests__/repl.test.ts:98 now passes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: repl.ts — withRetry around the initial streamAgent call

**Files:**

- Modify: `frontend/cli/repl.ts`
- Modify: `frontend/cli/__tests__/repl.test.ts`

**Step 1: Add failing tests**

Append to `repl.test.ts` (in a new `describe`):

```ts
describe("streamToTerminal: withRetry on initial call", () => {
  test("retries once on network error then succeeds", async () => {
    const netErr = Object.assign(new Error("fetch failed"), {
      code: "ECONNREFUSED",
    });
    mockedStreamAgent.mockImplementationOnce(() => {
      throw netErr;
    });
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: "token", content: "hi" }, { type: "done" }]),
    );
    await runRepl();
    expect(mockedStreamAgent).toHaveBeenCalledTimes(2);
  });

  test("does NOT retry on auth error", async () => {
    mockedStreamAgent.mockImplementationOnce(() => {
      throw new Error("Stream failed: 401");
    });
    await runRepl();
    expect(mockedStreamAgent).toHaveBeenCalledTimes(1);
    expect(mockedLog.error).toHaveBeenCalledWith(
      expect.stringMatching(/expired or unauthorized/i),
    );
  });
});
```

**Step 2: Run — FAIL** (current code calls `streamAgent` once and surfaces the throw).

**Step 3: Wrap the initial call**

In `streamToTerminal`, replace:

```ts
let current: EventStream = streamAgent(message, pageContext, { signal });
```

with:

```ts
let current: EventStream;
try {
  current = await withRetry(
    () => Promise.resolve(streamAgent(message, pageContext, { signal })),
    {
      maxAttempts: 2,
      signal: signal ?? new AbortController().signal,
      predicate: (e) => classifyError(e).retryable,
    },
  );
} catch (e) {
  process.stdout.write("\n");
  const c = classifyError(e);
  p.log.error(c.userMessage);
  if (c.hint) p.log.message(`  ${c.hint}`);
  return;
}
```

Add the import:

```ts
import { withRetry } from "./retry";
```

**Note:** `streamAgent` is a generator factory, not async — the throw happens when `loadConfig()` fails or fetch throws synchronously. Wrap in `Promise.resolve(...)` so withRetry's `await fn()` catches both sync and async throws.

**Step 4: Run — PASS**

Run: `npx jest cli/__tests__/repl.test.ts`

**Step 5: Commit**

```bash
git add frontend/cli/repl.ts frontend/cli/__tests__/repl.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): retry initial streamAgent on transient errors

Wraps the initial streamAgent call in withRetry. Predicate consults
classifyError so only network/transient_5xx/idle_timeout retry. Auth
and unknown bail out on first failure. streamConfirm intentionally
NOT wrapped (would risk double-triggering destructive tools).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: repl.ts — SIGINT scoped to in-flight stream

**Files:**

- Modify: `frontend/cli/repl.ts`
- Modify: `frontend/cli/__tests__/repl.test.ts`

**Step 1: Failing test**

Append to `repl.test.ts`:

```ts
describe("SIGINT scoping", () => {
  test("SIGINT mid-stream aborts the stream and returns to prompt (does not exit)", async () => {
    const exitSpy = jest
      .spyOn(process, "exit")
      .mockImplementation((() => undefined) as never);

    let abortRef: AbortSignal | undefined;
    mockedStreamAgent.mockImplementationOnce((_msg, _ctx, opts) => {
      abortRef = opts?.signal;
      return (async function* () {
        // wait until aborted
        await new Promise<void>((resolve) => {
          abortRef?.addEventListener("abort", () => resolve(), { once: true });
        });
        const e = new Error("aborted");
        e.name = "AbortError";
        throw e;
      })();
    });
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: "token", content: "second" }, { type: "done" }]),
    );

    // After first prompt, send SIGINT during stream
    setTimeout(() => process.emit("SIGINT" as never), 20);

    await runRepl();

    expect(exitSpy).not.toHaveBeenCalled();
    expect(abortRef?.aborted).toBe(true);
    exitSpy.mockRestore();
  });
});
```

**Step 2: Run — FAIL** (current SIGINT handler calls `process.exit(0)` unconditionally).

**Step 3: Refactor SIGINT installation**

Replace the unconditional `process.once('SIGINT', ...)` block in `runRepl` with a per-stream scoped install. Sketch:

```ts
// inside runRepl, replace:
//   process.once('SIGINT', () => { abort.abort(); p.outro('Bye.'); process.exit(0); });
// with nothing here. Install per-stream below.

let activeAbort: AbortController | null = null;
const onSigint = () => {
  if (activeAbort) {
    activeAbort.abort();
    return; // mid-stream → just cancel
  }
  p.outro("Bye.");
  process.exit(0);
};
process.on("SIGINT", onSigint);

try {
  // ...existing while loop...
  // before each streamToTerminal call:
  activeAbort = new AbortController();
  await streamToTerminal(input, ctx, activeAbort.signal);
  activeAbort = null;
  // ...
} finally {
  process.off("SIGINT", onSigint);
}
```

In `streamToTerminal`, catch the AbortError from the iterator and classify as `cancelled`:

```ts
try {
  for await (const event of current) {
    /* …existing… */
  }
} catch (e) {
  const c = classifyError(e);
  if (c.kind === "cancelled") {
    process.stdout.write("\n");
    p.log.warn("Cancelled.");
    return;
  }
  throw e;
}
```

**Step 4: Run — PASS** (and full suite still green).

Run: `npx jest cli/`

**Step 5: Commit**

```bash
git add frontend/cli/repl.ts frontend/cli/__tests__/repl.test.ts
git commit -m "$(cat <<'EOF'
fix(cli): scope SIGINT to in-flight stream, return to prompt on cancel

Old behavior: any Ctrl-C kills the process. New: Ctrl-C while a stream
is running aborts the stream and returns to the prompt; Ctrl-C at the
prompt exits as before. Stream's AbortError surfaces as a "Cancelled."
warning via the classifier.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: repl.ts — confirmKey raw-mode reader (single keystroke)

**Files:**

- Modify: `frontend/cli/repl.ts` (or extract into `frontend/cli/confirmKey.ts` if it grows)
- Modify: `frontend/cli/__tests__/repl.test.ts`

**Step 1: Failing test (non-TTY fallback)**

Append:

```ts
describe("confirmKey", () => {
  test("non-TTY path delegates to p.confirm and existing mocks still work", async () => {
    // Existing tests already mock p.confirm to return true. Just assert
    // the confirmation flow still completes without raw-mode interaction.
    mockedStreamAgent.mockReturnValueOnce(
      events([
        {
          type: "confirmation",
          threadId: "thread-x",
          details: { tools: [{ name: "create_project", args: {} }] },
        },
      ]),
    );
    mockedStreamConfirm.mockReturnValueOnce(events([{ type: "done" }]));
    await runRepl();
    expect(mockedConfirm).toHaveBeenCalled();
  });
});
```

**Step 2: Run** — should already PASS (existing behavior). Then proceed to make the swap without breaking.

**Step 3: Add `confirmKey` and replace `p.confirm` call**

New file `frontend/cli/confirmKey.ts`:

```ts
import * as p from "@clack/prompts";

export interface ConfirmKeyOptions {
  message: string;
  default?: boolean;
}

export async function confirmKey(
  opts: ConfirmKeyOptions,
): Promise<boolean | symbol> {
  const def = opts.default ?? true;
  if (!process.stdin.isTTY) {
    const r = await p.confirm({ message: opts.message });
    return r;
  }
  const suffix = def ? "[Y/n]" : "[y/N]";
  process.stdout.write(`${opts.message} ${suffix} `);
  return new Promise((resolve) => {
    const stdin = process.stdin;
    const wasRaw = stdin.isRaw;
    stdin.setRawMode?.(true);
    stdin.resume();
    const onData = (chunk: Buffer) => {
      const ch = chunk[0];
      stdin.off("data", onData);
      stdin.setRawMode?.(wasRaw ?? false);
      stdin.pause();
      process.stdout.write("\n");
      // Ctrl-C
      if (ch === 0x03) return resolve(p.isCancel as unknown as symbol);
      const c = String.fromCharCode(ch).toLowerCase();
      if (c === "y") return resolve(true);
      if (c === "n") return resolve(false);
      // Enter / anything else → default
      return resolve(def);
    };
    stdin.on("data", onData);
  });
}
```

In `repl.ts`, swap the confirmation call:

```ts
import { confirmKey } from "./confirmKey";
// …
const ok = await confirmKey({
  message: confirmationPromptMessage(event.details),
  default: true,
});
if (p.isCancel(ok) || !ok) {
  p.log.warn("Cancelled.");
  return;
}
```

The `p.confirm` mock in the test mocks `@clack/prompts.confirm` directly, and `confirmKey` calls it in the non-TTY branch — so the existing test setup continues to work without touching mocks.

**Step 4: Run full suite — PASS**

Run: `npx jest cli/`

**Step 5: Commit**

```bash
git add frontend/cli/confirmKey.ts frontend/cli/repl.ts frontend/cli/__tests__/repl.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): single-keystroke confirm in TTY, clack fallback elsewhere

confirmKey reads one byte in raw mode (y/n/Enter/Ctrl-C) so HITL
confirmations no longer require pressing Enter. Non-TTY (tests, pipes)
delegates to p.confirm to keep existing mocks working unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: repl.ts — /retry slash command

**Files:**

- Modify: `frontend/cli/repl.ts`
- Modify: `frontend/cli/prompt.ts` (add `/retry` to SLASH_COMMANDS for tab-completion)
- Modify: `frontend/cli/__tests__/repl.test.ts`

**Step 1: Failing tests**

Append:

```ts
describe("/retry", () => {
  test("re-runs the last user prompt against streamAgent", async () => {
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce("hi" as never)
      .mockResolvedValueOnce("/retry" as never)
      .mockResolvedValueOnce("__CANCEL__" as never);
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: "token", content: "first" }, { type: "done" }]),
    );
    mockedStreamAgent.mockReturnValueOnce(
      events([{ type: "token", content: "second" }, { type: "done" }]),
    );
    await runRepl();
    expect(mockedStreamAgent).toHaveBeenCalledTimes(2);
    expect(mockedStreamAgent).toHaveBeenNthCalledWith(
      1,
      "hi",
      expect.any(Object),
      expect.any(Object),
    );
    expect(mockedStreamAgent).toHaveBeenNthCalledWith(
      2,
      "hi",
      expect.any(Object),
      expect.any(Object),
    );
  });

  test("/retry with no prior message logs a hint and does not call streamAgent", async () => {
    mockedText.mockReset();
    mockedText
      .mockResolvedValueOnce("/retry" as never)
      .mockResolvedValueOnce("__CANCEL__" as never);
    await runRepl();
    expect(mockedStreamAgent).not.toHaveBeenCalled();
    const warnings = mockedLog.warn.mock.calls.map((c) => c[0] as string);
    expect(warnings.some((m) => /Nothing to retry/i.test(m))).toBe(true);
  });
});
```

**Step 2: Run — FAIL** (`/retry` falls through to streamAgent with literal `/retry`).

**Step 3: Implement**

In `runRepl`, add `let lastUserMessage: string | null = null;` near the other locals. Track every successful submission:

```ts
// inside the while-true loop, after streamToTerminal call:
lastUserMessage = input;
```

In `handleSlashCommand`, add a `/retry` branch. Since the handler doesn't have access to `lastUserMessage` today, thread it through `SlashContext`:

```ts
interface SlashContext {
  // …existing…
  lastUserMessage: string | null;
  retryLast: () => Promise<void>;
}
```

In `runRepl`'s call site:

```ts
const done = await handleSlashCommand(parsed.command, parsed.args, {
  // …existing…
  lastUserMessage,
  retryLast: async () => {
    if (!lastUserMessage) {
      p.log.warn("Nothing to retry.");
      return;
    }
    activeAbort = new AbortController();
    await streamToTerminal(lastUserMessage, ctx, activeAbort.signal);
    activeAbort = null;
  },
});
```

In `handleSlashCommand`:

```ts
if (command === "retry") {
  await ctx.retryLast();
  return true;
}
```

In `prompt.ts`, add `/retry` to `SLASH_COMMANDS`:

```ts
const SLASH_COMMANDS = [
  "/new",
  "/thread",
  "/threads",
  "/history",
  "/forget",
  "/projects",
  "/retry",
  "/context",
  "/settings",
  "/help",
  "/quit",
];
```

**Step 4: Run — PASS**

Run: `npx jest cli/__tests__/repl.test.ts cli/__tests__/prompt.test.ts`

**Step 5: Commit**

```bash
git add frontend/cli/repl.ts frontend/cli/prompt.ts frontend/cli/__tests__/repl.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): add /retry slash command

Re-emits the previous user message through the same streamToTerminal
path (so it gets withRetry + classifier handling). Empty case prints
"Nothing to retry." and is a no-op. Tab-completion learns it via
SLASH_COMMANDS.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: repl.ts — draft prefill on startup

**Files:**

- Modify: `frontend/cli/repl.ts`
- Modify: `frontend/cli/__tests__/repl.test.ts`

**Step 1: Failing test**

Append:

```ts
describe("draft restore on startup", () => {
  test("first readPrompt receives initialValue from ~/.nous/draft.txt; file is then empty", async () => {
    const draft = require("../services/draft");
    draft.writeDraft("half typed");
    mockedText.mockReset();
    mockedText.mockResolvedValueOnce("__CANCEL__" as never);
    await runRepl();
    expect(
      (mockedText.mock.calls[0]?.[0] as { initialValue?: string }).initialValue,
    ).toBe("half typed");
    expect(draft.readDraft()).toBe("");
  });
});
```

(Don't mock `services/draft` for this test — let it use the real `tmpConfigDir` already set in `beforeEach`.)

**Step 2: Run — FAIL**

**Step 3: Implement**

In `runRepl`, before the `while (true)` loop:

```ts
import { readDraft, clearDraft } from "./services/draft";
// …
let pendingDraft: string | null = null;
const initialDraft = readDraft();
if (initialDraft) {
  pendingDraft = initialDraft;
  clearDraft();
}
```

In the loop, when calling `readPrompt`:

```ts
const initialValue = pendingDraft ?? undefined;
pendingDraft = null;
const raw = await readPrompt({ message: ">", completer, initialValue });
```

**Step 4: Run — PASS**

Run: `npx jest cli/__tests__/repl.test.ts`

**Step 5: Commit**

```bash
git add frontend/cli/repl.ts frontend/cli/__tests__/repl.test.ts
git commit -m "$(cat <<'EOF'
feat(cli): restore in-progress draft on startup

If ~/.nous/draft.txt is non-empty at REPL launch, prefill the first
prompt with its contents and clear the file (one-shot). Combines with
the keypress writer to make Ctrl-C feel safe.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Final verification — type-check + full test suite

**Files:** none (verification only)

**Step 1: Type-check**

Run from `frontend/`:

```bash
npx tsc --noEmit
```

Expected: no output (clean).

**Step 2: Full CLI test suite**

```bash
npx jest cli/
```

Expected: ALL tests green. Specifically:

- `clears a missing confirmation thread` → **passes** (was the long-standing failure).
- ~+15 new tests across `errors.test.ts`, `retry.test.ts`, `services/draft.test.ts`, plus 4-6 new in `repl.test.ts` and `prompt.test.ts`.
- Target: ~100/100 instead of today's 84/85.

**Step 3: If any test fails**

- Read the failure carefully.
- If it's a regression (one of today's passing tests broke): `git diff HEAD~1 HEAD` on the offending task's commit, fix the regression, amend or new commit.
- If it's a new test that was supposed to pass and doesn't: do not delete the test. Either the implementation is wrong or the design is wrong. Fix the implementation, or stop and report.

**Step 4: No commit if step 1 + 2 are clean.** Move to Task 15.

---

## Task 15: Manual smoke test

**Files:** none (manual verification before merge)

Open one terminal and run the dev backend (`docker-compose -f docker-compose.development.yml up -d`). In a second terminal, from `frontend/`:

```bash
./nous
```

Run these three checks. Each one MUST pass before opening the PR.

**Smoke 1: Ctrl-C mid-stream returns to prompt**

- Send a prompt that triggers a long reply (e.g. `Summarise the latest arXiv paper on transformers in detail`).
- While tokens are streaming, press Ctrl-C **once**. You should see `Cancelled.` and a fresh `>` prompt — the process must NOT exit.
- Press Ctrl-C **again** at the empty prompt. The process should now exit cleanly with `Bye.`.

**Smoke 2: Backend down → friendly message**

- Stop the backend: `docker-compose -f docker-compose.development.yml stop backend`.
- In the running CLI, type any prompt and submit.
- You should see one line `Backend not reachable at http://localhost:8000/api/v1/agent/stream.` followed by `Set NOUS_API_URL or run /settings.`.
- The `>` prompt comes back ready for the next attempt.
- Restart the backend: `docker-compose -f docker-compose.development.yml start backend`. Confirm the next prompt works.

**Smoke 3: Draft survives Ctrl-C + relaunch**

- Type a long prompt: `this is a draft I do not want to lose if I exit accidentally`.
- Press Ctrl-C **without** submitting (one Ctrl-C at the prompt — should exit since no stream is in flight).
- Re-launch: `./nous`. The first prompt should be **prefilled** with the text you typed.
- Submit or clear it; relaunching again should NOT re-prefill (one-shot).

If any smoke check fails, the corresponding task's tests missed something. Add a test that reproduces the failure, fix the code, recommit.

---

## Done

Final state:

- 13 implementation commits (one per task) on `fix/hitl-post-confirm-ux`.
- `clears a missing confirmation thread` test passes.
- All three manual smoke checks green.
- Type-check clean.

Open the PR with the design doc linked in the description and the smoke test results in the test plan.
