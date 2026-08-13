# HITL/Memory Critical Fixes (R2-H1, R2-M2, R2-H4) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the three highest-impact findings from the 2026-08-13 agent-architecture audit: confirm-error runs stuck forever (H1), synthetic traffic polluting real users' memories (M2), and Redis-down double-confirm of destructive tools (H4).

**Architecture:** Three independent surgical fixes, one branch (`fix/hitl-confirm-lifecycle-critical`, off `origin/develop`), one commit per task. All backend Python. Repo worktree: `/Users/goodwiinz/development/RAG_system/.claude/worktrees/bridge-cse_01JdEJkzQhon6kHTQ8De977a`. Test venv: `/Users/goodwiinz/development/RAG_system/backend/.venv/bin` (run pytest from `backend/`). Style: Black 88 + isort on every touched file before committing.

**Tech Stack:** FastAPI SSE generator, SQLAlchemy async, Redis locks, pytest + AsyncMock.

**Ground rules:** Do NOT push or open a PR — commit locally only; the reviewer pushes. Do NOT touch files outside each task's list. The plan is a plan, not scripture — if a step contradicts the real code, say so in your report and do the right thing.

---

### Task 1: R2-H1 — finalize the durable run when /stream/confirm errors

**Problem:** In `stream_confirm_event_generator` (backend/src/api/agent/streaming.py), the `except Exception as e:` handler (~line 2780, log message "SSE stream confirm error") emits an ERROR frame and finishes the emitter but never finalizes the durable run. The job stays `awaiting_confirmation` forever; the thread reads as blocked. Compare: the cancellation path just above it calls `_finalize_run_id(db, job_id, current_user, status=JobStatus.CANCELLED, event_type=RunEventType.RUN_CANCELLED, payload=...)`.

**Files:**
- Modify: `backend/src/api/agent/streaming.py` (the confirm-generator `except Exception` block)
- Test: `backend/tests/unit/api/` — find the existing confirm-stream test file (`grep -rln "stream_confirm_event_generator" backend/tests/unit/api`) and add there; if none fits, create `backend/tests/unit/api/test_confirm_error_finalizes_run.py`.

**Step 1: Read the handler and the cancel path.** Confirm which variables are in scope in the except block: `db`, `current_user`, `active_run` (the cancel cleanup uses `str(active_run.job_id) if active_run is not None else None`), `emitter`. If `active_run` is not in scope at the except (defined later/conditionally), guard with `locals().get` — no, instead: check where `active_run` is bound; it is bound early in the generator (before the resume). Verify.

**Step 2: Write the failing test.** Shape: monkeypatch the resume path to raise, run the generator, assert `_finalize_run_id` (monkeypatched AsyncMock) was awaited with `status=JobStatus.FAILED`. Reuse the fixture style of the nearest existing confirm test (they build the generator with mock request/db/user). If building the full generator is impractical, an acceptable narrower test: extract the finalize-on-error into a small helper `_finalize_confirm_failure(db, active_run, current_user, error)` and unit-test THAT (helper called from the except block).

**Step 3: Implement.** In the except block, after `persist_partial_stop` and before/after the ERROR frame emit (order: finalize BEFORE emitting the error frame is fine; wrap in `contextlib.suppress(Exception)` so finalize failure can't mask the original error):

```python
        # R2-H1: an error at confirm time previously left the durable run
        # AWAITING_CONFIRMATION forever — the thread read as blocked and the
        # run never terminated. Finalize as FAILED (best-effort; the user
        # still gets the ERROR frame either way).
        with contextlib.suppress(Exception):
            await _finalize_run_id(
                db,
                str(active_run.job_id) if active_run is not None else None,
                current_user,
                status=JobStatus.FAILED,
                event_type=RunEventType.RUN_FAILED,
                payload={
                    "reason": "confirm_error",
                    "error": str(e)[:500],
                    "request_id": emitter.trace_id,
                },
            )
```

Match the exact `_finalize_run_id` signature and `RunEventType` member names used by the cancel path (read them; `RUN_FAILED` may be named differently — use whatever the enum actually has).

**Step 4: Run.** `cd backend && .venv-path/pytest <the test file> -q` → PASS. Then the confirm sweep: `pytest tests/unit/api -k "confirm" -q` → all green.

**Step 5: Commit.** `fix(agent): finalize run as FAILED when /stream/confirm errors (R2-H1)` + Co-Authored-By footer (Claude Opus 5 (1M context) <noreply@anthropic.com>).

### Task 2: R2-M2 — synthetic traffic must never fall back to a real user

**Problem:** `backend/scripts/synthetic_traffic.py` (~line 272): when the synthetic user insert loses a race / fails re-read, the bootstrap falls back to `select(User).where(User.is_active).limit(1)` — ANY real user — and the whole synthetic run (memories included, via the user-namespaced memory store) executes as that user. Tenant-purity violation on a */20min CronJob.

**Files:**
- Modify: `backend/scripts/synthetic_traffic.py`

**Step 1: Replace the fallback.** The insert is racing the re-read; the correct retry is to re-select the SYNTHETIC user (by `SYNTH_EMAIL`), briefly, then die loudly. Replace the fallback block with:

```python
        result = await db.execute(select(User).where(User.email == SYNTH_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            # Lost the insert race: the only acceptable retry is the SYNTHETIC
            # user itself. Never fall back to a real user — the entire run
            # (memory writes included) would execute in their namespace
            # (audit R2-M2). Dying loudly is fine: the CronJob retries in 20m.
            await asyncio.sleep(1.0)
            result = await db.execute(select(User).where(User.email == SYNTH_EMAIL))
            user = result.scalar_one_or_none()
            if user is None:
                raise RuntimeError(
                    "synthetic_traffic: synthetic user missing after insert; "
                    "refusing to run as a real user"
                )
            log.warning(
                "synthetic_traffic.bootstrap",
                action="reread_after_race",
                user_id=str(user.id),
            )
            return user
```

Check `asyncio` is imported in the script (it is a CLI async script; verify). Preserve everything after (workspace creation) untouched.

**Step 2: Verify.** `python -m py_compile backend/scripts/synthetic_traffic.py`. Check for an existing test harness: `grep -rln "synthetic_traffic" backend/tests` — if a bootstrap test exists, update it; if none, no new test required (script-level, covered by the CronJob's own failure visibility) — say so in the report.

**Step 3: Commit.** `fix(synthetic): never fall back to a real user in bootstrap (R2-M2)` + footer.

### Task 3: R2-H4 — in-process confirm claim when Redis is down

**Problem:** `backend/src/api/agent/streaming.py` (~line 2255): the HITL confirm claim (`hitl-confirm-claim:{thread}:{ckpt}`) is skipped entirely when `redis_client is None` (the existing `ponytail:` comment names this exact upgrade). Two concurrent `/stream/confirm` requests can then both issue `Command(resume=...)` → a destructive tool executes twice.

**Files:**
- Modify: `backend/src/api/agent/streaming.py`
- Test: `backend/tests/unit/api/test_confirm_claim_fallback.py` (new)

**Step 1: Write the failing test.** Two acquires of the same key with Redis unavailable: first True, second False; after expiry (monkeypatch `time.monotonic`), acquirable again. Test the helper directly.

**Step 2: Implement a module-level fallback in streaming.py** (near the confirm generator; mirror `job_store`'s in-memory pattern):

```python
# R2-H4: per-process confirm-claim fallback for Redis outages. Partial by
# design — it cannot see claims in OTHER workers (gunicorn multi-worker) —
# but it turns "no protection at all" into "protected within a worker",
# which closes the common single-worker dev/most-traffic case. The Redis
# claim remains authoritative when available.
_local_confirm_claims: dict[str, float] = {}
_local_confirm_claims_lock = threading.Lock()
_LOCAL_CONFIRM_TTL_S = 330.0


def _acquire_local_confirm_claim(key: str, now: Optional[float] = None) -> bool:
    """True if this process may proceed with the confirm; False if a live
    claim for the same key exists. TTL mirrors the Redis claim's 330s."""
    current = time.monotonic() if now is None else now
    with _local_confirm_claims_lock:
        expiry = _local_confirm_claims.get(key)
        if expiry is not None and expiry > current:
            return False
        _local_confirm_claims[key] = current + _LOCAL_CONFIRM_TTL_S
        # Opportunistic sweep so the dict can't grow unbounded.
        if len(_local_confirm_claims) > 512:
            for stale_key in [
                k for k, v in _local_confirm_claims.items() if v <= current
            ]:
                del _local_confirm_claims[stale_key]
        return True
```

Check `threading` / `time` imports at streaming.py top (add if missing). Then wire it: in the claim block, replace the bare "Redis down → no claim" path — when `redis_client is None` (and `resume_ckpt_id` present), call `_acquire_local_confirm_claim(confirm_claim_key)`; on False, emit the same "Confirmation already in progress" CONFLICT error frame and return. Also RELEASE on the same early-failure path where the Redis claim is released (`CX1` comment, `not events_started`): add a local release helper (`_release_local_confirm_claim(key)` → pop) called alongside `_release_lock` when the claim was local. Keep the Redis path byte-identical when Redis is up.

**Step 3: Run.** New test file green; `pytest tests/unit/api -k "confirm" -q` green; `python -m py_compile`.

**Step 4: Commit.** `fix(agent): in-process confirm-claim fallback for Redis outages (R2-H4)` + footer.

### Task 4: Final verification

- `cd backend && pytest tests/unit/api -k "streaming or confirm or persist" -q` — all green.
- `pytest tests/agent -q` — all green.
- Black + isort check on every touched file.
- Report per task: what changed, test evidence (pasted output lines), any deviations from this plan and why.
