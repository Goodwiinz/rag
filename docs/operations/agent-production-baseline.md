# Agent Production Baseline

This document defines the P0 operational contract for the NOUS agent. It is a
release gate, not an aspirational dashboard. Fast-path changes must satisfy the
latency, routing, durability, and stream-integrity checks below before the dev
image is promoted.

## Streaming contract

`POST /api/v1/agent/stream` uses Server-Sent Events. Every frame has:

- an SSE `id:` sequence used by `Last-Event-ID`;
- an `event:` from `AgentStreamEvent`;
- a JSON `data:` object with the event-specific fields plus:
  `schema_version`, `sequence`, `event_id`, `occurred_at`, `trace_id`,
  `thread_id`, and `route`.

Version `1.0` is **provisional**, not frozen. It describes what the current
implementation emits, and it stays changeable — including in
backward-incompatible ways — until P0-A's contract tests
(`docs/plans/2026-07-30-agent-audit-p0-pr-plan.md`) land. **P0-A is the freeze
event.** After P0-A, any breaking change to the envelope, event vocabulary, or
terminal semantics bumps `schema_version`; until then, do not describe `1.0` as
a compatibility guarantee to clients. The initial `accepted`
event has `thread_id: null` and `route: pending`: a client-supplied thread id
must not be echoed or buffered until ownership has been verified. Later frames
use only the ownership-resolved thread id and one of `luna`, `graph`, or
`unknown`.

Example:

```text
id: 2
event: status
data: {"phase":"routing","detail":"Using the direct Luna path","schema_version":"1.0","sequence":2,"event_id":"<trace>:2","occurred_at":"2026-07-30T03:00:00Z","trace_id":"<trace>","thread_id":"<owned-thread>","route":"luna"}
```

Reconnect with:

```http
GET /api/v1/agent/stream/resume/{thread_id}
Last-Event-ID: 17
Accept: text/event-stream
```

`?after=17` remains supported during the compatibility window. If both are
present, `Last-Event-ID` wins. Cursors are non-negative integer sequences.

## P0 service objectives

The bounded fast-path benchmark uses:

| Indicator               |                       Objective |
| ----------------------- | ------------------------------: |
| Samples                 |                     at least 20 |
| Failures                |                               0 |
| Accepted events         |                  one per sample |
| Accepted latency p95    |                       <= 250 ms |
| First-token latency p95 |                     <= 5,000 ms |
| Completion latency p95  |                     <= 5,000 ms |
| Route                   | 100% `luna` for the fast corpus |

Graph/research turns share accepted-event and stream-integrity requirements,
but require a task-class-specific completion SLO; they are not evaluated
against the five-second Luna completion budget.

## Metrics

The `/metrics` endpoint exposes:

- `agent_stream_accepted_duration_seconds`
- `agent_stream_first_token_duration_seconds{route}`
- `agent_stream_completion_duration_seconds{route}`
- `agent_stream_routes_total{route}`
- `agent_stream_turns_total{route,status}`

Example PromQL:

```promql
# Accepted p95
histogram_quantile(
  0.95,
  sum by (le) (rate(agent_stream_accepted_duration_seconds_bucket[10m]))
)

# Luna first-token p95
histogram_quantile(
  0.95,
  sum by (le) (
    rate(agent_stream_first_token_duration_seconds_bucket{route="luna"}[10m])
  )
)

# Luna completion p95
histogram_quantile(
  0.95,
  sum by (le) (
    rate(agent_stream_completion_duration_seconds_bucket{route="luna"}[10m])
  )
)

# Terminal error ratio
sum(rate(agent_stream_turns_total{status="error"}[10m]))
/
clamp_min(sum(rate(agent_stream_turns_total[10m])), 1)
```

Metric labels are server-owned and bounded. Never add organization, user,
thread, prompt, retrieved text, tool arguments, model output, exception text,
or arbitrary routing reasons as labels.

## Durability and readiness

The existing P0 foundations remain mandatory:

- deployed `dev`, `staging`, and `production` environments fail closed when
  PostgreSQL-backed agent state cannot initialize;
- `/health/readiness` checks critical dependencies and is the Kubernetes
  readiness probe;
- dev `/execute` uses the Celery `agent_runs` queue with a durable row,
  tenant-scoped idempotency key, execution lease, and stale-run sweeper;
- stream output is buffered for replay and successful assistant output is
  persisted/checkpointed before `done`.

Do not replace dependency-aware readiness with `/health`, enable in-memory
state in shared environments, or switch dev dispatch to `background` except as
an explicit incident rollback.

## Release command

Use a short-lived token and the non-production dev endpoint:

```sh
NOUS_BENCHMARK_TOKEN='<short-lived-token>' \
  backend/.venv/bin/python scripts/perf/benchmark_agent_fast_path.py \
  --base-url https://dev-api.gen-text.app \
  --samples 20 \
  --warmups 2 \
  --concurrency 1 \
  --target-accepted-p95-ms 250 \
  --target-first-token-p95-ms 5000 \
  --target-completion-p95-ms 5000 \
  --minimum-samples 20 \
  --required-route luna
```

The command exits non-zero and prints every failed criterion. Production hosts
are rejected by the benchmark harness.

## Rollback controls

- Fast path: set `AGENT_FAST_PATH_ENABLED=false`.
- Durable job dispatch: set `AGENT_DISPATCH_BACKEND=background` only as an
  explicit availability-over-durability incident action.
- Deployment: revert the dev image tag through GitOps and let ArgoCD reconcile.

Keep the SSE v1 envelope readable during rollback; removing envelope fields or
sequence ids is a breaking client change.
