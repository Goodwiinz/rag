# CLI Polish — Design

**Date:** 2026-04-26
**Status:** Approved (brainstorm complete; awaiting implementation plan)
**Scope:** UX friction + robustness/correctness for `frontend/cli/`. No backend changes. No new dependencies.

## Goals

1. Make the CLI feel safe to interrupt: `Ctrl-C` mid-turn cancels the stream and returns to the prompt rather than killing the process; in-progress input survives a relaunch.
2. Make errors actionable: every failure (network, auth, missing thread, transient 5xx, idle) classifies into a single shape with a one-line user message and an optional hint.
3. Fix the long-standing failing test (`clears a missing confirmation thread and retries the message once`) by removing the structural rot that produced it, not by patching the symptom.
4. Add two small features users have asked for: `/retry` to re-run the last prompt, and silent draft restore so a half-typed message is never lost.

## Non-goals

- Hooks (Claude-Code-style shell-command triggers). Worth doing — separate brainstorm. The classifier and retry helper introduced here become natural trigger points later.
- Visual/aesthetic polish (banners, brand colors, animations). Easy follow-up once foundations are solid.
- Cost policy or backend changes. Usage emission already shipped in PR-D.
- Streaming-loop state-machine rewrite. Considered (Approach 3 in brainstorm) and rejected as oversized for "polish".

## Architecture

Three new seams; everything else is in-place edits.

1. **Classification seam.** `cli/errors.ts` exports `classifyError(input) → ClassifiedError`. Pure function, no I/O. Both `streamToTerminal`'s SSE-error branch and the existing `handleSlashCommand` error paths consume the classified shape, so the failing test's "missing thread inside confirm flow" case becomes one branch in the classifier rather than two divergent code paths.
2. **Retry seam.** `cli/retry.ts` exports `withRetry(fn, opts)`. Used only around the _initial_ `streamAgent` call — never around `streamConfirm` (which has session state and could double-trigger destructive tools). Retries on `network` and `transient_5xx` and `idle_timeout` only. Reuses the existing `AbortController` so `Ctrl-C` still cancels mid-retry.
3. **Draft seam.** `cli/services/draft.ts` mirrors `promptHistory.ts`: read/write/clear at `~/.nous/draft.txt`. Written debounced (300ms) on every readline keypress, cleared synchronously on submit, prefilled (and cleared) once on startup.

`/retry` is a thin slash command — `runRepl` tracks `lastUserMessage`; the handler re-emits it through the same `streamToTerminal` call.

## Components

| File                         | New / Change | Purpose                                                                                                                                                                                                                               |
| ---------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cli/errors.ts`              | new          | `classifyError(input: unknown \| string \| StreamErrorEvent) → ClassifiedError`. Knows: `network`, `auth`, `not_found_thread`, `transient_5xx`, `idle_timeout`, `cancelled`, `unknown`.                                               |
| `cli/retry.ts`               | new          | `withRetry<T>(fn: (attempt: number) => Promise<T>, opts: { maxAttempts: number, signal: AbortSignal, predicate: (e: unknown) => boolean }): Promise<T>`. Fixed backoff: 250ms, 750ms.                                                 |
| `cli/services/draft.ts`      | new          | `readDraft()`, `writeDraft(text)`, `clearDraft()`. Path: `~/.nous/draft.txt`. Atomic via `writeFileSync`.                                                                                                                             |
| `cli/prompt.ts`              | change       | Accept `initialValue?: string`. Debounced (300ms) `writeDraft` on each keypress. `clearDraft()` on submit. Clack fallback unchanged.                                                                                                  |
| `cli/stream.ts`              | change       | Add `idleTimeoutMs?: number` (default 90000, env override `NOUS_STREAM_IDLE_MS`). Reset timer on every yielded event. On expiry: abort the fetch + yield sentinel `{ type: 'error', message: 'IDLE_TIMEOUT:90' }`.                    |
| `cli/services/client.ts`     | change       | When the underlying `fetch` throws, wrap into `Error` with the URL embedded so the classifier hint can include it.                                                                                                                    |
| `cli/repl.ts`                | change       | Track `lastUserMessage`. Wrap initial `streamAgent` in `withRetry`. Run all error events through `classifyError`. Prefill draft once on startup. Add `/retry` to dispatch. SIGINT handler installed only while a stream is in flight. |
| `cli/repl.ts` confirm prompt | change       | Replace `p.confirm(...)` with `confirmKey({ message, default: true })`: raw-mode single-keypress reader. Non-TTY → fall back to `p.confirm` so existing test mocks still work.                                                        |

## Error classifier mapping

```ts
type ErrorKind =
  | "network" // can't reach the server at all
  | "auth" // 401, 403, or local "not logged in"
  | "not_found_thread" // backend says the cached thread_id is gone
  | "transient_5xx" // 502/503/504, or our own idle timeout
  | "idle_timeout" // CLI gave up waiting for an event
  | "cancelled" // user hit Ctrl-C
  | "unknown"; // fall-through; not retryable

interface ClassifiedError {
  kind: ErrorKind;
  retryable: boolean;
  userMessage: string;
  hint?: string;
  raw?: unknown;
}
```

Mapping rules (ordered, first match wins):

| Input shape                                                                                             | → Kind             | retryable                                                                | userMessage / hint                                                       |
| ------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `Error.code` ∈ `{ECONNREFUSED, ENOTFOUND, EAI_AGAIN}` or message matches `/getaddrinfo\|fetch failed/i` | `network`          | yes                                                                      | `Backend not reachable at <url>.` / `Set NOUS_API_URL or run /settings.` |
| `Error.name === 'AbortError'`                                                                           | `cancelled`        | no                                                                       | `Cancelled.` / —                                                         |
| message matches `/not logged in\|401\|403\|unauthorized/i`                                              | `auth`             | no                                                                       | `Session expired or unauthorized.` / `Run ./nous login.`                 |
| message matches `/thread not found/i`                                                                   | `not_found_thread` | yes (consumed by REPL's existing fresh-thread retry, not by `withRetry`) | `Cached thread expired.` / `Starting a fresh thread…`                    |
| message matches `/Stream failed: 5\d\d/` or `/timeout\|timed out/i` (excluding IDLE_TIMEOUT sentinel)   | `transient_5xx`    | yes                                                                      | `Backend hiccup (HTTP 5xx).` / `Retrying once…`                          |
| sentinel `IDLE_TIMEOUT:<n>` from `stream.ts`                                                            | `idle_timeout`     | yes                                                                      | `Agent went silent at <n>s.` / `Retrying once…`                          |
| anything else                                                                                           | `unknown`          | no                                                                       | original message / —                                                     |

### Why this fixes the failing test

`streamToTerminal` today only clears the cached `thread_id` when `!inConfirmFlow`. The test sends a missing-thread error during the confirm flow and expects the cache to clear anyway. After this change, the confirm-flow branch also runs `classifyError(event.message)`; on `not_found_thread` it calls `clearCachedThreadId()` and prints the warning — same code path, no special-case for "first turn vs retry".

### Why `not_found_thread` retry is separate from `withRetry`

`withRetry` is a generic re-runner. The missing-thread path needs to mutate session state (clear `thread_id`, then re-issue from scratch). Coupling those would leak REPL internals into a generic helper.

### What never gets retried

`auth`, `cancelled`, `unknown`, and any error from inside a confirm-resume call (double-trigger risk for destructive tools).

## UX changes

**Ctrl-C inside a turn.** SIGINT handler installed only while a stream is in flight. On signal: `abort.abort()`, stream loop catches AbortError, classifies as `cancelled`, prints `Cancelled.`, returns to the prompt. Second Ctrl-C _at the prompt_ exits as today.

**Single-keystroke confirm.** `confirmKey({ message, default: true })`:

- TTY: raw mode, one byte. `y`/`Y` → true, `n`/`N` → false, `Enter` → default, `Ctrl-C` → cancel. Cooked mode restored in `finally`.
- Non-TTY: delegates to `p.confirm` so existing test mocks pass.
- Display: `Allow these 2 actions? [Y/n]` (capital = default).

**Draft restore.** Debounced 300ms `writeDraft` on each readline keypress. `clearDraft()` synchronously before `appendHistory` on submit. On startup: if file is non-empty, pass contents as `initialValue` to the first `readPrompt` call and clear the file (so it only restores once).

**Idle timeout.** `stream.ts` watchdog. Reset `setTimeout(idleTimeoutMs)` each loop iteration. On expiry: abort the fetch + yield `{ type: 'error', message: 'IDLE_TIMEOUT:90' }`. Default 90000ms; override via `NOUS_STREAM_IDLE_MS`.

**Friendlier connection errors.** `services/client.ts` wraps any `fetch` throw with the URL embedded so the classifier's `network` hint can be specific.

**`/retry` slash command.** New entry in `handleSlashCommand`. Re-emits `lastUserMessage` (tracked in `runRepl`'s loop scope) through the same `streamToTerminal` path. Empty → `Nothing to retry.`. Shares the same `withRetry`/classifier path as a fresh prompt.

## Testing strategy

**`cli/__tests__/errors.test.ts`** — pure unit tests for `classifyError`. One test per mapping table row. Edge cases: `null`/`undefined` → `unknown`, `Error` without message → `unknown`, nested `cause` (`new Error('x', { cause: { code: 'ECONNREFUSED' } })`) → `network`. ~15 tests, no mocks.

**`cli/__tests__/retry.test.ts`** — pure unit tests for `withRetry`:

- success on first attempt → no delay, no second call
- two retryable failures + success → 3 calls (or 2 with `maxAttempts: 2`)
- non-retryable predicate → throws on first failure, called once
- aborted signal → throws AbortError, no retry attempted
- backoff timing checked via `jest.useFakeTimers()`

**`cli/__tests__/services/draft.test.ts`** — same pattern as `promptHistory.test.ts`: `mkdtempSync` + `NOUS_CONFIG_DIR`. Empty read, round-trip, clear, malformed-file survival. ~5 tests.

**`cli/__tests__/repl.test.ts`** — extend existing suite:

1. **Resurrect failing test.** Same setup as today's broken test. After classifier fix, should pass without other changes. If it still fails, design is wrong — surface immediately.
2. **`/retry`** re-runs last prompt: type `hi`, stream completes, `/retry` → `streamAgent` called twice with `'hi'`.
3. **`/retry` with no prior message** → `Nothing to retry.` log, no `streamAgent` call.
4. **Network error triggers withRetry.** Mock `streamAgent` to throw `ECONNREFUSED` once then succeed; assert one `Retrying once…` warn and successful second call.
5. **Auth error does NOT retry.** Mock to throw `401` twice; assert only one `streamAgent` call and `auth` userMessage.
6. **Draft prefill on startup.** Pre-write `'half typed'` to draft file; assert `readPrompt` was called with `initialValue: 'half typed'` once, file empty after.

**`cli/__tests__/prompt.test.ts`** — extend with:

- `readPrompt` writes draft on each keypress (mock `process.stdin` + fake timers for the debounce)
- `confirmKey` non-TTY path delegates to `p.confirm`

**Manual smoke test (must pass before merge):**

1. `Ctrl-C` mid-streamed reply → returns to `>` prompt; second `Ctrl-C` exits.
2. Stop the backend, type a prompt → `Backend not reachable at <url>.` plus hint, prompt comes back ready.
3. Type a long prompt, `Ctrl-C` _without_ sending, relaunch → prompt is prefilled.

**Not tested.** Real readline keystrokes (too brittle in jsdom), real raw-mode confirm (TTY-dependent), real network. All covered by the manual smoke test.

## Coverage delta target

~+8 unit tests + ~6 integration-style tests in `repl.test.ts`. Lands at roughly 100/101 frontend CLI tests passing (vs today's 84/85), with the longstanding pre-existing failure finally green.

## Rejected alternatives

**Approach 1 (targeted fixes only).** Patches the failing test as a one-off, leaves ad-hoc error handling in place. Same surface, none of the structural fix.

**Approach 3 (streaming-loop state machine rewrite).** Cleanest end state but high regression risk and exceeds "polish" scope. The classifier + retry helper from Approach 2 are natural slots if a future state-machine rewrite happens.

**Bundling hooks (Claude-Code-style PostTurn / PreToolUse).** Real value but a separate feature, not polish. Designing both at once means hooks get poor triggers and polish gets distracted. Defer to a follow-up brainstorm; the classifier/retry helpers introduced here become its trigger points.
