# Task 17 Report: Stabilize Semantic Judge Inputs

## Status

Complete. The no-tools Azure judge now disables reasoning while retaining its
800-token output budget. Writing and KB semantic judging now score only the
user-visible final assistant message; raw tool output remains available as
trusted evidence and to deterministic Layer A checks. KG remains unchanged and
continues to judge only its final assistant message.

## Exact Files Changed

- `evals/harbor_common/judge.py`
- `evals/harbor_common/selftest.py`
- `evals/agent-writing-flow-v1/tests/verify.py`
- `evals/agent-kb-retrieval-v1/tests/verify.py`
- `.superpowers/sdd/2026-08-10-agent-benchmark-failure-remediation/task-17-report.md`

`evals/agent-full-benchmark-v1.json` was preserved, left unstaged, and excluded
from the Task 17 commit.

## TDD Evidence

RED before the harness edits:

- The judge-constructor capture failed because `reasoning_effort` was absent.
- The task-input capture failed because writing's candidate serialized both the
  visible answer and the raw `compare_documents_result`.

GREEN after the three minimal edits:

- The constructor capture proves `reasoning_effort="none"` and the unchanged
  `max_tokens=800` budget.
- Writing's candidate is exactly the visible final message; its raw comparison
  is present in `trusted_sources`.
- KB's candidate is exactly the visible final message; retrieved chunks remain
  in `trusted_sources`.
- KG's captured candidate remains exactly its visible final message.
- `evals/harbor_common/selftest.py`: exit `0`, `selftest ok`.

## Calibration Matrix

| Task | Fixture | Expected | Actual |
| --- | --- | ---: | ---: |
| KB | `pass.json` | 0 | 0 |
| KB | `empty-kb-honest.json` | 0 | 0 |
| KB | `wrong-hallucinated-grounding.json` | 10 | 10 |
| Writing | `pass.json` | 0 | 0 |
| Writing | `wrong-premature-draft.json` | 10 | 10 |
| KG | `pass.json` | 0 | 0 |
| KG | `empty-kg-honest.json` | 0 | 0 |
| KG | `wrong-cross-tenant.json` | 10 | 10 |

Calibration verdict stubs remain gated by `BENCHMARK_CALIBRATION_FIXTURE`; no
live evidence can self-certify.

## Static Validation

- Python compile: passed for all four owned Python files.
- Black: passed for all four owned Python files.
- Ruff: passed for all four owned Python files.
- JSON parsing: passed for KB, writing, and KG task JSON files.
- `git diff --check`: passed.
- Harbor: not run, as required; Task 19 owns the live affected-suite run.

## Preserved Judge Behavior

The deployment, strict verdict schema, three attempts, 25-second request
timeout, 100-second wall budget, JSON-mode fallback, and infrastructure-failure
classification are unchanged.

## Commit

`fix(evals): stabilize semantic judge inputs`
