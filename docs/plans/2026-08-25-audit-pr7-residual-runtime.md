# Reviewed Plan: PR7 Residual Runtime Correctness

Fable verdict: **APPROVE WITH REQUIRED CHANGES**. This plan incorporates them.

Target: `origin/develop` at `1b7ce43808b8ae82ab60e2d2b2193cd9d880fc3a`

Branch: `codex/audit-pr7-runtime-residuals`

## Scope

Close R2-M8, R2-M13, R2-L9, and R2-L17 only. Do not use Tambo. Do not add dependencies, migrations, or unrelated cleanup.

## 1. R2-L9 — atomic thread counters

In `backend/src/services/threads/chat_service.py`, replace both ORM read-modify-write sites (`create_message` and `create_assistant_message`) with the existing SQLAlchemy atomic expression pattern from `backend/src/services/agent/agent_submission_service.py:293-301`:

- `message_count = coalesce(message_count, 0) + 1`
- `token_count = coalesce(token_count, 0) + delta`
- set `last_message_at` in the same update
- `synchronize_session=False`

Refresh the thread after commit before the `message_count >= 3` summarization threshold because async sessions use `expire_on_commit=False` and the update deliberately bypasses synchronization. Cover both writers with a focused regression and keep `test_transaction_ownership.py` green.

## 2. R2-M13 — stale-run sweeper fails safe

In `backend/src/tasks/agent_run_tasks.py`, distinguish a `get_job_fresh()` exception from a successful missing payload. On exception: increment `skipped` and continue without changing run status and **without releasing the 300-second sweeper lease**. The lease must self-expire; releasing it could reopen execution while live state is unknown. Preserve existing terminal repair and successful-missing behavior. Add a sweeper regression using the existing `_sweep` harness proving the run stays running and the lease remains held.

## 3. R2-M8 — tokenized summary in-flight exclusion

In `backend/src/services/threads/thread_summarization_service.py`, retain the existing cooldown key and add a separate `thread_summary:{id}:inflight` key:

- acquire before any generation with `SET key <random-token> NX EX <bounded lease>`
- `force=True` bypasses cooldown only; it must still respect the in-flight key
- Redis failures remain degrade-safe and do not block summarization
- successful LLM, fallback, and timeout-fallback persistence convert to the existing 300-second cooldown
- release the in-flight key only for non-persisting exits, using token-safe Lua compare-and-delete so an expired/reacquired lock cannot be deleted
- no lock class or dependency

Extend `backend/tests/services/threads/test_summary_rate_limit_paths.py`: held in-flight lock blocks force; exceptions release only the caller token; persisted success/timeout retains cooldown and clears in-flight ownership.

## 4. R2-L17 — worker consumes latent queues

Append `text_processing,vector_processing` to the Celery worker `-Q` list in `infrastructure/helm/knowledge-graph-analytics/templates/celery-worker-deployment.yaml`. These paths are latent/retry-only today; do not claim active production publishers. Add `task_queues` entries in `backend/src/tasks/celery_app.py` only if required by an existing configuration invariant; Celery auto-creation means Helm consumption is the essential fix. Add one guard test ensuring every queue in `processing_service.py`'s dispatch map is consumed by the worker.

## Plan artifact

Add this reviewed plan to `docs/plans/2026-08-25-audit-pr7-residual-runtime.md` in the PR.

## Verification

Run focused tests, `test_transaction_ownership.py`, pinned Ruff/Black/isort on changed Python, `scripts/ci/run_local_ci.sh --base origin/develop`, and `git diff --check`. Report environmental skips honestly. Leave changes uncommitted for orchestrator review.
