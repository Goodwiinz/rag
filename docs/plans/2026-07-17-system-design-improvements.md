# System-Design Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the highest-value gaps identified by the 2026-07-16 deep-research pass and its Codex second opinion: the enqueue/commit ordering race class, semantic API-compatibility gating, unit-of-work transaction ownership, deterministic concurrency testing for the chat store, Alembic CI depth, and a single-owner contract for server state.

**Architecture:** Six independently mergeable PRs off `origin/develop`, in risk order: the live race class first, then CI gates, then the transaction-boundary refactor (behavior-preserving, behind the existing characterization suites), then test-infrastructure and docs. Every PR passes the quality ratchets shipped by the maintainability program (changed-file gates, added-file strict mypy, coverage floors, OpenAPI zero-drift).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2 async, Celery, Alembic, pytest; TypeScript, Vitest, Zustand; GitHub Actions, oasdiff.

**Inputs & provenance:**
- Deep-research synthesis (24 claims, 3-0 verified) + Codex second opinion (gpt-5.6-sol, 2026-07-16) — scratchpad `research-synthesis.md`.
- Codex verdicts: [a] add oasdiff atop the raw drift gate; [b] deterministic interleaving tests over recurring manual mutation; [c] UoW at the use-case layer, leaf services `flush()`; [d] enqueue/commit race in `documents.py`, TanStack↔Zustand ownership, Alembic depth, pnpm `workspace:`.
- Overlaps the standing system-design audit ledger (`~/.audit-ledgers/rag/system-design-2026-07-10.md`): durability trio X1–X3, missing-reconciler D1–D7, contract drift C1–C7. Mark ledger items when a PR closes them.

**Verified ground truth (2026-07-17, develop @ `93fb8f7f`):**
- `backend/src/api/documents/documents.py:1352-1365`: `db.add(job)` → `flush()` → `.delay(job_id)` → `commit()`. The ordering is deliberate (comment: broker-down ⇒ rollback, no orphan row) but leaves the worker-consumes-before-commit race. Eight backend files contain enqueue sites (`.delay(`/`send_task`).
- `backend/src/services/threads/thread_service.py:87` has `commit: bool = False` — the exact flag pattern Codex warned breeds ambiguity.
- Alembic CI guard (`scripts/ci/check_alembic.py` + `migration-check` job) checks single-head + revision-id length only.
- The committed mutation evidence (`docs/testing/chat-mutation-checks.md`) covers **7 guard groups** (1, 2, 3, 4a, 4b, 5, 6) — not "16 guards"; PR 6 corrects that number where stated.

---

## Delivery rules

- Each PR branches from latest `origin/develop`; PRs are file-disjoint except where noted; base every PR on `develop` (never on a sibling — see the stranded-merge lesson in project memory).
- TDD: failing test → minimal change → focused suite → full lane. Behavior-preserving PRs (3) require characterization green before movement.
- Every PR must pass: changed-file ruff/black/isort, added-file strict mypy (CI lint venv has NO runtime deps — verify with a bare venv: `pip install ruff==0.15.15 black==26.5.1 isort==5.13.2 mypy==1.7.1`), OpenAPI `generate_openapi.py --check` + `pnpm --dir frontend generate:api-types` zero-drift, and the frontend ratchets when frontend files change.
- Never share an `AsyncSession` across concurrent tasks; never weaken tenant scope; keep `deprecated=True` flags.

## Dependency map

| PR | Branch | Depends on | Risk |
| --- | --- | --- | --- |
| 1 | `fix/enqueue-after-commit` | — | behavior change (safe direction), live race |
| 2 | `ci/oasdiff-compat-gate` | — | CI only |
| 3 | `refactor/uow-transaction-ownership` | ideally after 1 (shares service files) | behavior-preserving refactor |
| 4 | `test/chat-deterministic-interleavings` | — | tests only |
| 5 | `ci/alembic-depth` | — | CI only |
| 6 | `docs/state-ownership-and-corrections` | after 4 (references its harness) | docs + guard test |

---

## PR 1: Enqueue-after-commit with a lost-job reconciler

Closes the worker-reads-before-commit race without reintroducing the orphan-row
problem the current ordering was built to avoid. Ledger: contributes to X1–X3
(durability) and D-class (reconciler).

### Task 1.1: Characterize the race and inventory the class

**Files:**
- Create: `backend/tests/unit/tasks/test_enqueue_ordering.py`
- Read: `backend/src/api/documents/documents.py:1330-1375`
- Read: the 8 enqueue-site files (`rg -l '\.delay\(|send_task' backend/src`)

**Step 1: Write the inventory test (red).** A stdlib AST test that walks
`backend/src` and, for every function containing both a Celery enqueue call
(`.delay(`, `.apply_async(`, `send_task(`) and an `await db.commit()`/
`await self.db.commit()`, asserts the enqueue is NOT positionally before the
commit — unless the call site is routed through the `enqueue_after_commit`
helper (Task 1.2) or carries an explicit
`# enqueue-before-commit: <justification>` comment. Expected initially: FAIL
listing `documents.py` (and any sibling sites the walk finds — record the
measured list in the PR description).

**Step 2: Run it, record the measured offender list.**
Run: `backend/.venv pytest -q backend/tests/unit/tasks/test_enqueue_ordering.py`
Expected: FAIL with the offender inventory.

**Step 3: Commit the red test** (`test(tasks): inventory enqueue-before-commit sites`).

### Task 1.2: `enqueue_after_commit` helper (the root fix, once)

**Files:**
- Create: `backend/src/tasks/enqueue.py`
- Create: `backend/tests/unit/tasks/test_enqueue_after_commit.py`

**Step 1: Failing tests first.** Behaviors to pin:
- registered callbacks fire **only after** a successful commit (use SQLAlchemy
  `event.listens_for(session.sync_session, "after_commit")` semantics through the
  async session; in tests use an in-memory SQLite async session);
- callbacks are **dropped on rollback** (no fire);
- a callback that raises logs (structlog) but does not corrupt the session state;
- multiple registrations fire in order.

**Step 2: Implement minimal helper.**
```python
def enqueue_after_commit(db: AsyncSession, task, *args, **kwargs) -> None:
    """Register a Celery enqueue to run only after this session commits.

    Solves both orderings' failure modes: no worker-reads-before-commit race
    (fires post-commit), and no orphaned rows on broker failure (an enqueue
    error after commit is repaired by the reconciler, Task 1.4).
    """
    sync_session = db.sync_session

    @event.listens_for(sync_session, "after_commit", once=True)
    def _fire(_session) -> None:
        try:
            task.delay(*args, **kwargs)
        except Exception:
            logger.exception("enqueue_after_commit_failed", task=task.name)
```
(Exact listener mechanics to be settled against the installed SQLAlchemy version
in Step 1's tests — `once=True` vs manual deregistration, and rollback pruning
via `after_soft_rollback`. The tests are the contract, not this sketch.)

**Steps 3-5:** green, ruff/black/isort/mypy (added file ⇒ strict), commit
(`feat(tasks): post-commit enqueue helper`).

### Task 1.3: Migrate the offender sites

**Files:**
- Modify: `backend/src/api/documents/documents.py` (reprocess + upload paths)
- Modify: each site from Task 1.1's measured inventory
- Modify: `backend/tests/unit/tasks/test_enqueue_ordering.py` (flips green)

One commit per file. Preserve each site's response shape. Where a site
intentionally must enqueue pre-commit, keep it with the justification comment —
the AST test enforces the comment exists. Run each file's focused tests
(`backend/tests/api/...` siblings) after its migration.

### Task 1.4: Lost-job reconciler (closes the post-commit enqueue-failure window)

**Files:**
- Create: `backend/src/tasks/reconcile_jobs.py`
- Create: `backend/tests/unit/tasks/test_reconcile_jobs.py`
- Modify: `backend/src/tasks/celery_app.py` (beat schedule — CAUTION: memory
  records an open "beat_schedule clobber" issue; ADD to the schedule dict,
  verify no key collision, and add a regression test that all expected beat
  entries coexist)

**Behavior (tests first):** a periodic task selects `ProcessingJob` rows with
`status == PENDING` and `celery_task_id IS NULL` older than N minutes
(default 10, config-driven), re-enqueues each via `.delay(job_id)`, stamps an
attempt counter, and gives up (status FAILED + structlog) after M attempts
(default 3). Must be tenant-agnostic (system task) but must NOT touch rows in
other states. Idempotent: double-run yields no duplicate enqueues (guard on a
`reconciled_at`/attempt column — if a migration is needed, single new Alembic
revision, one head preserved).

### PR 1 verification

```bash
pytest -q backend/tests/unit/tasks backend/tests/api/documents 2>/dev/null || pytest -q backend/tests/unit/tasks
ruff check backend/src ; changed-file black/isort ; added-file strict mypy (bare venv)
ENVIRONMENT=testing DATABASE_URL=sqlite:///:memory: [AZURE dummies] python scripts/ci/generate_openapi.py --check
git diff --check origin/develop...HEAD
```

---

## PR 2: oasdiff semantic compatibility gate (advisory → ERR-blocking)

Codex [a]: the raw both-artifact diff gate is stricter on freshness but blind to
compatibility — a breaking change that regenerates both artifacts passes. Ledger: C-class.

### Task 2.1: Advisory oasdiff job

**Files:**
- Modify: `.github/workflows/test-pipeline.yml` (extend `openapi-contract` job)
- Create: `backend/tests/unit/ci/test_oasdiff_gate.py`

**Step 1: Failing workflow-contract test** (same pattern as
`test_contract_job_verifies_generated_typescript`): assert the job (a) obtains
the BASE branch's `backend/openapi.json` (via `git show
origin/${BASE}:backend/openapi.json > /tmp/openapi-base.json` with
`fetch-depth: 0` already present), (b) runs `oasdiff breaking
/tmp/openapi-base.json backend/openapi.json`, (c) the step is explicitly
labeled `Advisory` with `continue-on-error: true` at this stage.

**Step 2: Implement the step** using the pinned oasdiff binary (install via
`go install` or the release tarball — pin the version; document in the step).
On PRs only (skip on push-to-develop where BASE is meaningless).

**Step 3-4:** green; commit (`ci(openapi): advisory breaking-change gate`).

### Task 2.2: Blocking policy for ERR-level changes

**Files:** same, plus `docs/engineering/api-contracts.md`

After one week advisory (or immediately if the team prefers — record the
choice): split into two steps — `oasdiff breaking --fail-on ERR` (blocking) and
`oasdiff changelog` (informational job summary). Update the workflow-contract
test to require the blocking step and the Advisory label to be gone. Document
the escape hatch (a deliberate breaking change lands with an
`api-breaking-approved` PR label the job honors — implement via `if:` guard).

---

## PR 3: Unit-of-work transaction ownership (kills `commit: bool` flags)

Codex [c]: "every service commits" blocks composing services atomically and
breeds `commit=True` flags. Target state: the request/use-case layer owns
`async with db.begin()`; leaf services `flush()` only. This is a
behavior-preserving refactor over the freshly characterized workspace surface —
the 4.1 route-contract test + services suites are the safety net.

### Task 3.1: Characterize current commit semantics

**Files:**
- Create: `backend/tests/unit/services/threads/test_transaction_ownership.py`

Pin current behavior per service function: which functions commit, which flush,
what `commit: bool` defaults do (`thread_service.py:87`). These tests will be
UPDATED (not deleted) as tasks flip functions to flush-only — each flip is a
deliberate, reviewed edit.

### Task 3.2: Introduce the UoW at the route layer, one resource at a time

**Files:**
- Modify: `backend/src/api/threads/workspace_routes/{workspaces,members,conversations,threads,messages,collections}.py`
- Modify: `backend/src/services/threads/{workspace,conversation,thread,message,collection}_service.py`
- Modify: `backend/src/services/threads/chat_service.py` (compat delegates)

Order: collections → members → workspaces → conversations → threads → messages
(smallest blast radius first). Per resource: route handler wraps its mutating
path in `async with db.begin()` (or explicit commit at handler end where
`begin()` conflicts with the session middleware — measure against the actual
`request.state.db` lifecycle first and record which pattern the codebase
supports); service loses its `commit()` calls in favor of `flush()`;
`commit: bool` parameters deleted; post-create re-fetch behavior preserved
(`expire_on_commit` semantics verified by the existing
create-then-read characterization tests). The 4.4 architecture guard
(`test_workspace_boundaries.py`) must be UPDATED in the same commit as each flip
so the guard always describes reality.

**Hard constraints:** wire shapes unchanged (OpenAPI zero-drift after every
resource); `enqueue_after_commit` (PR 1) keeps firing at the right time —
its after_commit listener is what makes service-level flush safe here.

### Task 3.3: Architecture guard ratchet

Extend `test_workspace_boundaries.py`: after the flips, `commit(` is forbidden
in `backend/src/services/threads/*_service.py` (allowlist: `chat_service.py`
compat delegates until callers migrate — with a removal condition documented).

---

## PR 4: Deterministic interleaving harness for the chat store

Codex [b]: manual guard-removal was a valid one-time audit; the durable strategy
is deterministic, property-driven interleaving tests.

### Task 4.1: Scheduler test utility

**Files:**
- Create: `frontend/src/test/concurrency/deferredScheduler.ts`
- Create: `frontend/src/test/concurrency/__tests__/deferredScheduler.test.ts`

A tiny utility: `createDeferred<T>()` (promise + resolve/reject) and
`runInterleaving(steps: Step[])` that executes an explicit, seedless ordering of
async operations (start/resolve/reject actions referencing named deferreds).
No new dependencies (YAGNI: no fast-check yet — table-driven orderings first;
fast-check can arrive later if tables prove insufficient).

### Task 4.2: Table-driven orderings for the 7 guard groups

**Files:**
- Create: `frontend/src/test/concurrency/__tests__/chatStore.interleavings.test.ts`
- Read: `docs/testing/chat-mutation-checks.md` (the 7 groups)

For each guard group (stale-response/newest-page identity; expectation
reconciliation; thread-scope turn gating; HITL confirm idempotency; HITL
thread-scope; submit single-flight; loadOlder commit-phase), enumerate the
orderings that matter: A-start → B-start → B-resolve → A-resolve (classic
stale), A→B→A re-entry, reject-then-resolve, unmount/clear-mid-flight. Each
row: seed store state, run the interleaving via the scheduler, assert the
invariant (B's transcript intact, exactly one stream, no duplicate submit...).
Reuse the existing service-mock patterns from `chat-store-refresh.test.ts`.

### Task 4.3: Two automated mutants as meta-tests

**Files:**
- Create: `scripts/ci/run_chat_mutants.mjs`
- Modify: `frontend/package.json` (script `test:mutants`)

Script applies each defined mutant (a small string-replacement patch that
disables one guard — e.g. the `newestPageRequests` generation check), runs the
covering interleaving test, REQUIRES failure, restores the file byte-identical
(verify via git diff), and exits non-zero if any mutant survives. Two mutants
only (stale-response + submit single-flight) — the point is a living meta-test,
not a mutation platform. NOT wired into blocking CI initially; add as an
advisory job step.

---

## PR 5: Alembic CI depth

Codex [d]: current guard = single-head + id-length. Add execution-level checks.
CAUTION from memory: analytics tables have no create-migration and dev crash-
looped on this before (PR #720 to_regclass guard) — the from-empty upgrade may
legitimately fail today; Task 5.1 measures before gating.

### Task 5.1: Measure `upgrade head` from empty (advisory)

**Files:**
- Modify: `.github/workflows/test-pipeline.yml` (extend `migration-check` with a
  Postgres 15 service container)
- Create: `backend/tests/unit/ci/test_migration_check_workflow.py` (contract test)

Step: `alembic upgrade head` against the empty service DB, then
`alembic check` (model↔migration drift), then `alembic downgrade -1 && alembic
upgrade head`. All `continue-on-error: true` + labeled Advisory in this task.
Record the measured result in the PR description.

### Task 5.2: Ratchet to blocking

Flip `upgrade head`-from-empty to blocking once green (fix revealed migration
gaps in separate commits if small; file follow-up issues if structural).
`alembic check` and the downgrade smoke stay advisory until their debt is
measured at zero — same honest-gate doctrine as PR 2 of the maintainability
program.

---

## PR 6: State-ownership contract, docs corrections, guard

### Task 6.1: Single-owner rule for server state

**Files:**
- Modify: `docs/engineering/frontend.md`
- Modify: `frontend/src/test/architecture/__tests__/maintenanceContracts.test.ts`

Document the rule (TanStack Query owns request-backed server state; the chat
Zustand store is the ONE exception as the server-canonical chat transcript
owner; a given server entity has exactly one cache owner; Server Actions must
not become a third). Guard test: files under `frontend/src/store/chat/` must not
import `@tanstack/react-query`, and files using `useQuery` for
workspace/thread/message entities must not also read those entities from the
chat store (implement the narrow, mechanical half: the import ban; document the
rest as review guidance — do not build a heuristic analyzer, YAGNI).

### Task 6.2: Corrections and small chores

**Files:**
- Modify: `docs/testing/chat-mutation-checks.md` (state "7 guard groups"
  wherever "16 guards" appears; link PR 4's harness as the successor practice)
- Modify: `docs/engineering/api-contracts.md` (JSONB nuance per Codex: typed
  JSONB CAN be modeled in Pydantic/OpenAPI; handwritten is for intentionally
  opaque JSON + view-model shapes only)
- Modify: `docs/engineering/README.md` (pnpm `workspace:` protocol note for
  future internal packages)

### Task 6.3: Ledger reconciliation

Update `~/.audit-ledgers/rag/system-design-2026-07-10.md`: mark the items PRs
1/2/5 close (durability/reconciler/contract-drift entries), with PR numbers.
Update memory `project_maintainability_foundation_plan.md` pointer to this plan.

---

## Final acceptance

- PR 1: AST inventory test green (no unjustified enqueue-before-commit);
  reconciler tests green; beat-schedule coexistence test green.
- PR 2: oasdiff ERR-blocking on PRs with documented escape hatch.
- PR 3: zero `commit: bool` parameters in `services/threads`; architecture guard
  updated; OpenAPI zero-drift maintained throughout.
- PR 4: 7 guard groups covered by deterministic interleavings; 2 mutants killed
  by the meta-test script.
- PR 5: from-empty `upgrade head` blocking; drift/downgrade advisory with
  measured baseline.
- PR 6: ownership rule documented + import-ban guard green; docs corrected.
- All: maintainability-program ratchets pass unchanged.
