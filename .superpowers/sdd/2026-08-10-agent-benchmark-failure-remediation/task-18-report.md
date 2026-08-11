# Task 18 report: poll graph-stream disconnects before keepalive

## Summary

`_graph_events_with_keepalive` now checks for disconnects every 0.5 seconds
while the graph's `__anext__` is pending. The heartbeat deadline remains
independent at 10 seconds, so polling does not emit extra heartbeat frames.

The helper uses `asyncio.wait(..., timeout=...)`, so no sleep task exists to
leak. Its existing `finally` now cancels and awaits any pending graph pull. The
existing disconnect sentinel and caller cleanup remain the only durability
owners; no service, worker, or endpoint was added.

## TDD evidence

RED, before the production edit:

- Focused keepalive suite: 1 failed, 2 passed.
- The post-check disconnect test timed out at 0.1 seconds while the helper was
  still waiting for the patched 0.2-second heartbeat.

GREEN, after the production edit:

- Focused keepalive suite: 3 passed.
- Requested cancellation regressions: 7 passed, 3 skipped.
- The skipped prefix/linkage integration cases require PostgreSQL at
  `localhost:54322`, which refused connections. Response abort, buffered
  disconnect, and repeated-cancellation tests passed locally.

## Calibration and static gates

| Gate | Expected | Actual |
| --- | ---: | ---: |
| `pass.json` | 0 | 0 |
| `wrong-late-completion.json` | 10 | 10 |
| Python compile | pass | pass |
| Black check | pass | pass |
| Ruff check | pass | pass |
| JSON parse | pass | pass |
| `git diff --check` | pass | pass |

Harbor was not run, as required. The intentional
`evals/agent-full-benchmark-v1.json` worktree modification was not edited or
staged.

## Commit

`fix(agent): poll stream disconnects before keepalive`

## Fix round 1/5

The disconnect sentinel previously escaped while the pending graph
`__anext__` task still owned the async generator. The outer cancellation path
could then suppress `RuntimeError` from `aclose()` and leave cleanup to delayed
finalization.

Both disconnect-sentinel branches now cancel and await any pending pull under
`BaseException` suppression, clear `pending`, and only then yield the sentinel.
The existing `finally` remains idempotent. Event completion, event errors,
`StopAsyncIteration`, the 0.5-second poll, and the 10-second heartbeat are
unchanged.

The focused regression now uses a real async generator and asserts its
`finally` completed before the caller receives the sentinel, then immediately
calls `aclose()`. It failed before the production edit and passes after it.

- Focused keepalive suite: 3 passed.
- Cancellation regressions: 8 passed, 3 skipped because PostgreSQL at
  `localhost:54322` refused connections.
- Calibration: `pass.json` returned 0; `wrong-late-completion.json` returned 10.
- Compile, Black, Ruff, JSON parse, and `git diff --check`: passed.
- Harbor was not run. The intentional benchmark JSON was not edited or staged.

Commit: `fix(agent): settle pending pull before disconnect sentinel`

## Fix round 2/5

Round 1 awaited the cancelled graph pull inside
`suppress(BaseException)`. A concurrent ASGI cancellation could therefore
escape that await, be suppressed, and let the helper yield a disconnect
sentinel before async-generator cleanup finished.

Disconnect handling now clears ownership from `pending`, cancels the pull, and
repeatedly shields it until it settles. If the current task is cancelled during
that wait, the first `CancelledError` is remembered and re-raised after cleanup;
the disconnect sentinel is not yielded. Ordinary request disconnects still
receive the sentinel, but only after the pull has settled. The existing
`finally` remains idempotent, and poll/heartbeat timing is unchanged.

The deterministic regression blocks the pull's async-generator `finally`,
delivers two ordered ASGI cancellations, and proves that propagation waits for
cleanup, preserves the original cancellation args, and yields no sentinel. It
failed against round 1 and passes after the fix. The ordinary sentinel-ordering
test remains green.

- Focused and cancellation regressions: 8 passed, 3 PostgreSQL-dependent tests
  skipped because `localhost:54322` refused connections.
- Stream-cancel calibration: `pass.json` returned 0;
  `wrong-late-completion.json` returned 10.
- Compile, Black, Ruff, isort, benchmark/calibration JSON parse, and
  `git diff --check`: passed.
- Harbor was not run. The intentional benchmark JSON modification was neither
  edited nor staged.

## Fix round 3/5

The keepalive helper's `finally` still directly awaited its pending graph pull,
so an initial ASGI cancellation followed by another cancellation during the
async generator's cleanup could abort that cleanup. The existing helper also
treated the repeated cancellation as newly arriving and could replace the
original cancellation's arguments.

The `finally` path now clears `pending` once and delegates its sole await to
`_cancel_pending_graph_pull`. The helper records whether cancellation was
already active at entry: that path settles the graph pull through repeated
cancellations without raising a replacement, while a first cancellation that
arrives inside the helper is still captured and re-raised after cleanup.

The deterministic regression cancels while the graph pull is pending, waits
for async-generator cleanup to start, then cancels again. Before the production
edit it failed because cleanup never completed; after the edit cleanup finishes
and the propagated `CancelledError` retains `("original ASGI cancellation",)`.
The prior concurrent-inside-helper and ordinary disconnect tests remain green.

- Focused keepalive suite: 5 passed.
- Cancellation regressions: 4 passed, 3 skipped because PostgreSQL at
  `localhost:54322` refused connections.
- Stream-cancel calibration: `pass.json` returned 0;
  `wrong-late-completion.json` returned 10.
- Compile, Black, Ruff, isort, benchmark/calibration JSON parse, and
  `git diff --check`: passed.
- Harbor was not run. The intentional benchmark JSON modification was neither
  edited nor staged.

Commit: `fix(agent): settle graph pull during cancellation`
