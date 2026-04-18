# Agent Evals — NOUS Agent v2

Two evaluation suites for benchmarking coding agents against the NOUS agent v2 system.

## 1. V2 Module Implementation (`tasks/v2-modules/`)

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

## 2. Regression (`tasks/regression/`)

Tests whether an agent can make changes to the v2 system **without breaking existing tests**.
Pinned to commit `98a17bb` (full v2 implementation, 145-test regression suite).

| Task                      | Scenario                    | Judge                         |
| ------------------------- | --------------------------- | ----------------------------- |
| `add-tool.yaml`           | Add a new agent tool        | 145 existing + new tests      |
| `modify-classifier.yaml`  | Add a new intent category   | All classifier tests pass     |
| `extend-error-hints.yaml` | Add new error hints         | All error recovery tests pass |
| `refactor-compactor.yaml` | Change compaction threshold | All compactor tests pass      |

## Usage

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
