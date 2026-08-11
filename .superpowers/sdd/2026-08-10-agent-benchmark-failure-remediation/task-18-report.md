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
