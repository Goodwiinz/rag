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
