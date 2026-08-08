# Agent evaluations

This directory contains production-flow Harbor benchmarks for the deployed NOUS
agent and the older coding-agent suites.

## Production agent-flow benchmarks (Harbor)

These tasks execute pinned production code against isolated PostgreSQL, Redis,
and deterministic service doubles. The main task container has no unrestricted
egress: a Squid sidecar permits only the configured model host, and every task
records positive and negative network probes.

| Task | Capability | Primary verifier |
| --- | --- | --- |
| `agent-direct-project-action-v1` | Route, confirm, and execute a direct project action | Deterministic trajectory plus PostgreSQL state |
| `rag-retrieval-safety-grounding-v1` | Safely postprocess, rerank, and synthesize noisy KB results | Deterministic safety/provenance gates plus isolated semantic judge |
| `agent-stream-cancel-durability-v1` | Make client Stop terminal and durable at the production SSE API | Deterministic SSE, PostgreSQL, Redis, and resume checks |
| `agent-project-management-v1` | Route, approve, and execute a multi-step project-management flow | Deterministic trajectory, HITL snapshots, and PostgreSQL state |
| `agent-writing-flow-v1` | Compare documents, draft (HITL, async fake-success trap), and export a bibliography | Deterministic trajectory, HITL snapshots, PostgreSQL state, and an isolated semantic judge |
| `agent-kb-retrieval-v1` | Search indexed documents, then retrieve and cite grounded guidance from the org knowledge base | Deterministic trajectory, mock-KB auth/network probes, and an isolated semantic judge |

`agent-writing-flow-v1` and `agent-kb-retrieval-v1` are judge-gated: Layer B
(`harbor_common.judge.run_semantic_judge`) only runs after every Layer A
(deterministic) check passes, and both are NOT YET GATED in
`AGENT_FLOW_BASELINE.md` — awaiting their first recorded run.

Tasks added after 2026-08-07 import their adapter and verifier helpers from the
shared `harbor_common/` package; the original three tasks keep their inline
copies and stay pinned by their existing digests.

The approved capability, Environment, and Harness contracts are under `specs/`.
The pinned baseline and audit are in `baselines/agent-flow-2026-08-04.json` and
`AGENT_FLOW_BASELINE.md`. Generated trial evidence is intentionally ignored by
Git but retained locally under `jobs/` until the evaluation is accepted.

Run a task from the repository root with Harbor 0.6.6 and approved model/judge
environment variables already present. The private production dependency image
`registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1` must also be
available locally or pullable with registry authentication; its expected digest
is recorded in each `task.toml`:

```bash
harbor run \
  --path evals/agent-direct-project-action-v1 \
  --agent-import-path evals.harbor_agents.nous_production_agent:NousProductionAgent \
  --env docker \
  --jobs-dir evals/jobs \
  --job-name agent-direct-project-action-v1-<revision> \
  --force-build \
  --n-concurrent 1 \
  --yes
```

Replace the task path and job name for the other benchmarks (including
`agent-writing-flow-v1` and `agent-kb-retrieval-v1`). Do not reuse a
prior score after the task digest, repository revision, or Harness digest in
`source-manifests/` changes. An adapter, dependency, credential, reset, timeout,
judge, or verifier failure is infrastructure and must not be scored as agent
reward 0.

## Coding-agent suites

Two legacy suites benchmark coding agents against the NOUS agent v2 system.

### 1. V2 Module Implementation (`tasks/v2-modules/`)

Tests whether an agent can correctly implement each v2 module **from the plan spec**.
Pinned to commit `6af5432` (pre-v2 — only the design doc and plan exist, no implementation).

Each task gives the agent the design doc as context + a focused prompt.
Because `6af5432` predates the dedicated v2 test files, each judge pulls the
matching test file from commit `98a17bb` via `git show` into a temporary file
before running `pytest`.

| Task                  | Module            | Judge           |
| --------------------- | ----------------- | --------------- |
| `error-recovery.yaml` | error_recovery.py | 10 pytest tests |
| `classifier.yaml`     | classifier.py     | 24 pytest tests |
| `compactor.yaml`      | compactor.py      | 24 pytest tests |
| `planner.yaml`        | planner.py        | 6 pytest tests  |
| `reflection.yaml`     | reflection.py     | 9 pytest tests  |
| `memory-store.yaml`   | memory_store.py   | 9 pytest tests  |

### 2. Regression (`tasks/regression/`)

Tests whether an agent can make changes to the v2 system **without breaking existing tests**.
Pinned to commit `98a17bb` (full v2 implementation, 145-test regression suite).

| Task                      | Scenario                    | Judge                         |
| ------------------------- | --------------------------- | ----------------------------- |
| `add-tool.yaml`           | Add a new agent tool        | 145 existing + new tests      |
| `modify-classifier.yaml`  | Add a new intent category   | All classifier tests pass     |
| `extend-error-hints.yaml` | Add new error hints         | All error recovery tests pass |
| `refactor-compactor.yaml` | Change compaction threshold | All compactor tests pass      |

### Usage

```bash
# Install agent-eval (see https://github.com/joaquinhuigomez/agent-eval)

# Run a single task
agent-eval run --task evals/tasks/v2-modules/error-recovery.yaml --agent claude-code --runs 3

# Run all v2 module tasks
agent-eval run --task evals/tasks/v2-modules/ --agent claude-code --agent aider --runs 3

# Run regression suite
agent-eval run --task evals/tasks/regression/ --agent claude-code --runs 3

# Generate report
agent-eval report --format table
```
