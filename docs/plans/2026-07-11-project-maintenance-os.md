# Project Maintenance OS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a private local dashboard that monitors RAG_system, coordinates Codex and Claude investigations, creates tested draft pull requests, and requires approval for restricted actions.

**Architecture:** Add a separate `maintenance_os` application with a FastAPI control service, SQLite state store, and Next.js dashboard. Collectors normalize local Git and GitHub/CI events into durable work items; a policy engine gates actions; an agent runner uses isolated worktrees and streams evidence to the UI.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, SQLite, Alembic, Pydantic, pytest, Next.js 16, React 18, TypeScript, Vitest, Playwright, pnpm 10.18.2, Server-Sent Events.

---

## Implementation rules

- Work only in the dedicated `design/project-maintenance-os` worktree.
- Follow TDD: add one failing behavior, prove the failure, implement the minimum, prove the pass, then commit.
- Bind both services to `127.0.0.1`; do not add public ingress, authentication providers, Redis, Celery, or production deployment manifests in the MVP.
- Store no secrets in SQLite. Collectors read credentials from the process environment or existing authenticated CLIs.
- All editing jobs use isolated Git worktrees. Do not modify the operator's active checkout.
- Use the pinned root package manager: `corepack pnpm@10.18.2`.
- Every restricted action must be denied unless a current approval matches its action, target, and evidence revision.

### Task 1: Scaffold the local API and dashboard packages

**Files:**
- Create: `maintenance_os/api/pyproject.toml`
- Create: `maintenance_os/api/src/maintenance_os/__init__.py`
- Create: `maintenance_os/api/src/maintenance_os/config.py`
- Create: `maintenance_os/api/src/maintenance_os/main.py`
- Create: `maintenance_os/api/tests/test_health.py`
- Create: `maintenance_os/dashboard/package.json`
- Create: `maintenance_os/dashboard/tsconfig.json`
- Create: `maintenance_os/dashboard/next.config.ts`
- Create: `maintenance_os/dashboard/vitest.config.ts`
- Create: `maintenance_os/dashboard/vitest.setup.ts`
- Create: `maintenance_os/dashboard/app/layout.tsx`
- Create: `maintenance_os/dashboard/app/page.tsx`
- Create: `maintenance_os/dashboard/app/globals.css`
- Create: `maintenance_os/dashboard/src/__tests__/smoke.test.tsx`
- Modify: `pnpm-workspace.yaml`
- Modify: `pnpm-lock.yaml`

**Step 1: Write the failing API health test**

```python
from fastapi.testclient import TestClient

from maintenance_os.main import app


def test_health_is_local_control_plane() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "maintenance-os"}
```

**Step 2: Run it and verify failure**

Run:

```bash
cd maintenance_os/api
uv run pytest tests/test_health.py -v
```

Expected: FAIL because `maintenance_os.main` does not exist.

**Step 3: Add the minimal Python package and health route**

`maintenance_os/api/pyproject.toml`:

```toml
[project]
name = "nous-maintenance-os"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "alembic>=1.18,<2",
  "fastapi>=0.138,<1",
  "httpx>=0.28,<1",
  "pydantic-settings>=2.14,<3",
  "sqlalchemy>=2.0,<3",
  "sse-starlette>=1.6,<2",
  "uvicorn[standard]>=0.49,<1",
]

[dependency-groups]
dev = ["pytest>=9,<10", "pytest-asyncio>=1.4,<2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/maintenance_os"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

`maintenance_os/api/src/maintenance_os/config.py`:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAINTENANCE_OS_")

    host: str = "127.0.0.1"
    port: int = 8787
    repository_path: Path
    data_dir: Path = Path(".maintenance-os")


def get_settings() -> Settings:
    return Settings()
```

`maintenance_os/api/src/maintenance_os/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Project Maintenance OS")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "maintenance-os"}
```

**Step 4: Run the API test and verify pass**

Run: `cd maintenance_os/api && uv run pytest tests/test_health.py -v`

Expected: PASS.

**Step 5: Add the dashboard smoke test and minimal shell**

`maintenance_os/dashboard/src/__tests__/smoke.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import Home from "../../app/page";

it("identifies the maintenance control plane", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { name: /project maintenance os/i })).toBeInTheDocument();
});
```

The minimal page renders the heading and the sentence `Local control plane for RAG_system`.

Add `maintenance_os/dashboard` to `pnpm-workspace.yaml`, install Next, React, TypeScript, Vitest, jsdom, and Testing Library, and define scripts `dev`, `build`, `test`, and `type-check`.

**Step 6: Run the dashboard test and workspace checks**

Run:

```bash
corepack pnpm@10.18.2 install --lockfile-only
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard type-check
```

Expected: both commands PASS.

**Step 7: Commit**

```bash
git add maintenance_os pnpm-workspace.yaml pnpm-lock.yaml
git commit -m "feat(maintenance-os): scaffold local control plane"
```

### Task 2: Add the SQLite schema and state machine

**Files:**
- Create: `maintenance_os/api/alembic.ini`
- Create: `maintenance_os/api/alembic/env.py`
- Create: `maintenance_os/api/alembic/versions/0001_initial_state.py`
- Create: `maintenance_os/api/src/maintenance_os/db.py`
- Create: `maintenance_os/api/src/maintenance_os/domain.py`
- Create: `maintenance_os/api/src/maintenance_os/models.py`
- Create: `maintenance_os/api/src/maintenance_os/repositories/work_items.py`
- Create: `maintenance_os/api/tests/test_work_item_state.py`
- Create: `maintenance_os/api/tests/test_audit_log.py`

**Step 1: Write failing state-transition tests**

```python
import pytest

from maintenance_os.domain import WorkItemState, transition


def test_investigation_can_wait_for_approval() -> None:
    assert transition(WorkItemState.INVESTIGATING, WorkItemState.WAITING_APPROVAL) is WorkItemState.WAITING_APPROVAL


def test_completed_item_cannot_return_to_executing() -> None:
    with pytest.raises(ValueError, match="illegal transition"):
        transition(WorkItemState.COMPLETED, WorkItemState.EXECUTING)
```

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/test_work_item_state.py -v`

Expected: FAIL because the domain module does not exist.

**Step 3: Implement the state machine**

```python
from enum import StrEnum


class WorkItemState(StrEnum):
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


ALLOWED: dict[WorkItemState, set[WorkItemState]] = {
    WorkItemState.QUEUED: {WorkItemState.INVESTIGATING, WorkItemState.DISMISSED},
    WorkItemState.INVESTIGATING: {WorkItemState.WAITING_APPROVAL, WorkItemState.EXECUTING, WorkItemState.BLOCKED},
    WorkItemState.WAITING_APPROVAL: {WorkItemState.EXECUTING, WorkItemState.DISMISSED, WorkItemState.BLOCKED},
    WorkItemState.EXECUTING: {WorkItemState.VERIFYING, WorkItemState.BLOCKED},
    WorkItemState.VERIFYING: {WorkItemState.COMPLETED, WorkItemState.BLOCKED},
    WorkItemState.BLOCKED: {WorkItemState.QUEUED, WorkItemState.DISMISSED},
    WorkItemState.COMPLETED: set(),
    WorkItemState.DISMISSED: set(),
    WorkItemState.SUPERSEDED: set(),
}


def transition(current: WorkItemState, target: WorkItemState) -> WorkItemState:
    if target not in ALLOWED[current]:
        raise ValueError(f"illegal transition: {current} -> {target}")
    return target
```

**Step 4: Define and migrate durable records**

Create SQLAlchemy models for `signals`, `work_items`, `claims`, `investigations`, `findings`, `changes`, `approvals`, and `audit_events`. Every table uses UUID text primary keys and UTC timestamps. `audit_events` is insert-only at the repository layer. Add unique constraints for signal source keys, active claim work-item IDs, and action idempotency keys.

**Step 5: Test persistence and append-only audit behavior**

Use a temporary SQLite database. Prove that a transition creates an audit event in the same transaction and that the repository exposes no update/delete method for audit events.

Run: `cd maintenance_os/api && uv run pytest tests/test_work_item_state.py tests/test_audit_log.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): persist work-item state"
```

### Task 3: Enforce the approval policy

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/policy.py`
- Create: `maintenance_os/api/src/maintenance_os/services/approvals.py`
- Create: `maintenance_os/api/tests/test_policy.py`
- Create: `maintenance_os/api/tests/test_approval_freshness.py`

**Step 1: Write failing policy tests**

```python
from maintenance_os.policy import Action, Decision, PolicyContext, decide


def test_draft_pr_is_allowed_without_approval() -> None:
    context = PolicyContext(target_revision="abc", evidence_revision="e1", approval=None)
    assert decide(Action.CREATE_DRAFT_PR, context) is Decision.ALLOW


def test_merge_is_denied_without_approval() -> None:
    context = PolicyContext(target_revision="abc", evidence_revision="e1", approval=None)
    assert decide(Action.MERGE_PR, context) is Decision.DENY


def test_stale_approval_is_denied() -> None:
    approval = approved(Action.MERGE_PR, target_revision="old", evidence_revision="e1")
    context = PolicyContext(target_revision="new", evidence_revision="e1", approval=approval)
    assert decide(Action.MERGE_PR, context) is Decision.DENY
```

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/test_policy.py -v`

Expected: FAIL because `policy.py` does not exist.

**Step 3: Implement explicit action classes**

```python
class Action(StrEnum):
    READ = "read"
    INVESTIGATE = "investigate"
    RUN_TESTS = "run_tests"
    CREATE_DRAFT_PR = "create_draft_pr"
    MERGE_PR = "merge_pr"
    DEPLOY = "deploy"
    CHANGE_INFRASTRUCTURE = "change_infrastructure"
    ACCESS_SECRET = "access_secret"


UNRESTRICTED = {Action.READ, Action.INVESTIGATE, Action.RUN_TESTS, Action.CREATE_DRAFT_PR}
RESTRICTED = set(Action) - UNRESTRICTED
```

`decide` allows unrestricted actions and requires an unexpired approval whose action, target revision, and evidence revision exactly match for restricted actions.

**Step 4: Add approval service and transactional consumption**

Create an approval record with `requested`, `approved`, `rejected`, `consumed`, and `expired` states. `consume_approval` rechecks policy and changes `approved -> consumed` atomically before the action runs.

**Step 5: Run policy suite**

Run: `cd maintenance_os/api && uv run pytest tests/test_policy.py tests/test_approval_freshness.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): enforce approval boundaries"
```

### Task 4: Collect local Git and GitHub CI signals

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/collectors/base.py`
- Create: `maintenance_os/api/src/maintenance_os/collectors/local_git.py`
- Create: `maintenance_os/api/src/maintenance_os/collectors/github.py`
- Create: `maintenance_os/api/src/maintenance_os/services/collection.py`
- Create: `maintenance_os/api/tests/collectors/test_local_git.py`
- Create: `maintenance_os/api/tests/collectors/test_github.py`
- Create: `maintenance_os/api/tests/fixtures/github/pr_checks.json`

**Step 1: Write a failing local Git collector test**

Initialize a temporary repository with one commit, one modified file, and one untracked file. Assert the collector returns the HEAD SHA, branch, upstream divergence, and dirty paths without mutating the repository.

```python
snapshot = LocalGitCollector(repo).collect()
assert snapshot.branch == "develop"
assert snapshot.modified == ["tracked.txt"]
assert snapshot.untracked == ["new.txt"]
```

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/collectors/test_local_git.py -v`

Expected: FAIL because the collector does not exist.

**Step 3: Implement read-only local Git collection**

Use `git status --porcelain=v2 --branch -z`, `git rev-parse HEAD`, and `git worktree list --porcelain`. Run commands with argument arrays, a fixed repository cwd, timeouts, captured output, and no shell.

**Step 4: Add the GitHub/CI contract test**

Mock `httpx.AsyncClient` with the recorded fixture. Verify that pull-request and check-run data preserve repository, PR number, head SHA, job name, status, conclusion, URL, and updated time.

**Step 5: Implement the GitHub collector**

Read `GITHUB_TOKEN` and `GITHUB_REPOSITORY` from environment. If unavailable, return collector status `unknown` with a diagnostic; never report green. Normalize GitHub API responses into `SignalInput` records with stable source keys such as `github:check-run:<id>:<updated_at>`.

**Step 6: Run collector tests**

Run: `cd maintenance_os/api && uv run pytest tests/collectors -v`

Expected: PASS.

**Step 7: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): collect git and CI signals"
```

### Task 5: Reconcile signals into prioritized work

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/services/reconcile.py`
- Create: `maintenance_os/api/src/maintenance_os/services/prioritize.py`
- Create: `maintenance_os/api/tests/test_reconcile.py`
- Create: `maintenance_os/api/tests/test_prioritize.py`

**Step 1: Write failing deduplication tests**

```python
def test_repeated_failure_updates_one_work_item(store) -> None:
    first = signal(source_key="ci:run:42", kind="ci_failed", revision="a")
    repeated = signal(source_key="ci:run:42", kind="ci_failed", revision="a")
    reconcile(store, [first, repeated])
    assert store.count_work_items() == 1
    assert store.count_signal_links() == 2
```

Also prove that a later passing run supersedes the failure only when the head SHA matches; a green run for a different SHA does not resolve it.

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/test_reconcile.py -v`

Expected: FAIL because reconciliation does not exist.

**Step 3: Implement reconciliation**

Use a deterministic fingerprint from repository, kind, subject, and target revision. Link every source signal for provenance. Preserve the highest observed severity and newest evidence. Mark a work item superseded only through explicit resolution rules.

**Step 4: Add and implement priority scoring**

```python
score = (
    severity_weight[item.severity]
    + 20 * item.blocks_release
    + 15 * item.is_security
    + 10 * item.is_regression
    + freshness_bonus(item.updated_at)
    + round(item.confidence * 10)
)
```

Unknown or stale source health lowers confidence but does not erase the work item. Tie-break by oldest unresolved timestamp.

**Step 5: Run tests**

Run: `cd maintenance_os/api && uv run pytest tests/test_reconcile.py tests/test_prioritize.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): reconcile and prioritize work"
```

### Task 6: Coordinate claims, worktrees, and agent adapters

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/agents/base.py`
- Create: `maintenance_os/api/src/maintenance_os/agents/codex.py`
- Create: `maintenance_os/api/src/maintenance_os/agents/claude.py`
- Create: `maintenance_os/api/src/maintenance_os/services/claims.py`
- Create: `maintenance_os/api/src/maintenance_os/services/worktrees.py`
- Create: `maintenance_os/api/src/maintenance_os/services/runner.py`
- Create: `maintenance_os/api/tests/test_claims.py`
- Create: `maintenance_os/api/tests/test_worktrees.py`
- Create: `maintenance_os/api/tests/test_runner.py`

**Step 1: Write failing exclusive-claim tests**

Prove that only one active claim exists per work item, an expired claim may be replaced, and a heartbeat cannot revive an expired claim.

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/test_claims.py -v`

Expected: FAIL because the claim service does not exist.

**Step 3: Implement claims and worktree creation**

Create worktrees under `<data_dir>/worktrees/<investigation-id>` from `origin/develop` using argument-array subprocess calls. Record base SHA and path before agent launch. Refuse to reuse a non-empty path or operate in the configured source checkout.

**Step 4: Define the shared agent protocol**

```python
@dataclass(frozen=True)
class AgentJob:
    investigation_id: str
    prompt: str
    worktree: Path
    timeout_seconds: int


@dataclass(frozen=True)
class AgentResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class AgentAdapter(Protocol):
    async def run(self, job: AgentJob, emit: EventSink) -> AgentResult: ...
```

Codex and Claude adapters build fixed command arrays, stream sanitized stdout/stderr events, enforce timeout, and terminate the process group on cancellation. Do not use `shell=True`.

**Step 5: Test timeout and partial evidence**

Use a fake executable that writes one event and sleeps. Assert timeout preserves the first event, marks the investigation blocked, and releases the claim without deleting the worktree.

**Step 6: Run tests**

Run: `cd maintenance_os/api && uv run pytest tests/test_claims.py tests/test_worktrees.py tests/test_runner.py -v`

Expected: PASS.

**Step 7: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): run claimed agent investigations"
```

### Task 7: Expose the control API and event stream

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/api/dependencies.py`
- Create: `maintenance_os/api/src/maintenance_os/api/schemas.py`
- Create: `maintenance_os/api/src/maintenance_os/api/today.py`
- Create: `maintenance_os/api/src/maintenance_os/api/work_items.py`
- Create: `maintenance_os/api/src/maintenance_os/api/agents.py`
- Create: `maintenance_os/api/src/maintenance_os/api/approvals.py`
- Create: `maintenance_os/api/src/maintenance_os/api/events.py`
- Modify: `maintenance_os/api/src/maintenance_os/main.py`
- Create: `maintenance_os/api/tests/api/test_today.py`
- Create: `maintenance_os/api/tests/api/test_work_items.py`
- Create: `maintenance_os/api/tests/api/test_approvals.py`
- Create: `maintenance_os/api/tests/api/test_events.py`

**Step 1: Write failing Today API test**

```python
def test_today_separates_attention_work_and_approvals(client, seeded_store) -> None:
    response = client.get("/api/today")
    assert response.status_code == 200
    body = response.json()
    assert body["needs_attention"][0]["state"] == "blocked"
    assert body["active_investigations"][0]["state"] == "investigating"
    assert body["pending_approvals"][0]["action"] == "merge_pr"
```

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/api/test_today.py -v`

Expected: FAIL with 404.

**Step 3: Implement read and command routes**

Add:

- `GET /api/today`
- `GET /api/work-items`
- `GET /api/work-items/{id}`
- `POST /api/work-items/{id}/investigate`
- `POST /api/work-items/{id}/pause`
- `POST /api/work-items/{id}/reprioritize`
- `GET /api/investigations/{id}`
- `GET /api/approvals`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`
- `GET /api/activity`

Command endpoints require `Idempotency-Key`, validate current state, and append an audit event transactionally.

**Step 4: Add the SSE test and implementation**

`GET /api/events` returns `text/event-stream`, starts with a `snapshot` event, emits events with monotonic IDs, and sends a heartbeat every 15 seconds. Test event formatting through the event broker directly rather than waiting 15 seconds.

**Step 5: Run API tests**

Run: `cd maintenance_os/api && uv run pytest tests/api -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/api
git commit -m "feat(maintenance-os): expose control API"
```

### Task 8: Build the Today dashboard

**Files:**
- Create: `maintenance_os/dashboard/src/lib/api.ts`
- Create: `maintenance_os/dashboard/src/lib/types.ts`
- Create: `maintenance_os/dashboard/src/hooks/useMaintenanceEvents.ts`
- Create: `maintenance_os/dashboard/src/components/AppShell.tsx`
- Create: `maintenance_os/dashboard/src/components/HealthStrip.tsx`
- Create: `maintenance_os/dashboard/src/components/AttentionList.tsx`
- Create: `maintenance_os/dashboard/src/components/ActiveWork.tsx`
- Create: `maintenance_os/dashboard/src/components/ApprovalSummary.tsx`
- Modify: `maintenance_os/dashboard/app/layout.tsx`
- Modify: `maintenance_os/dashboard/app/page.tsx`
- Create: `maintenance_os/dashboard/src/__tests__/today.test.tsx`

**Step 1: Write the failing Today view test**

Mock `GET /api/today` and assert the page renders `Needs attention`, `Active work`, and `Waiting for you`, preserves evidence/confidence labels, and does not render a source with `unknown` health as green.

**Step 2: Run and verify failure**

Run: `corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test -- today.test.tsx`

Expected: FAIL because the components do not exist.

**Step 3: Implement typed API access and the dashboard shell**

Use `NEXT_PUBLIC_MAINTENANCE_OS_API=http://127.0.0.1:8787` with a local default. Keep navigation to Today, Work Queue, Agents, Changes, Incidents, Knowledge, and Activity. Implement clear `observed`, `inferred`, `stale`, and `unknown` badges.

**Step 4: Add SSE refresh behavior**

`useMaintenanceEvents` reconnects with bounded exponential backoff, remembers `lastEventId`, and invalidates the Today fetch on relevant events. A disconnected event stream shows `Live updates disconnected`; it does not erase the last snapshot.

**Step 5: Run frontend checks**

Run:

```bash
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard type-check
```

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/dashboard
git commit -m "feat(maintenance-os): add Today dashboard"
```

### Task 9: Add queue, evidence, agents, approvals, and activity views

**Files:**
- Create: `maintenance_os/dashboard/app/work/page.tsx`
- Create: `maintenance_os/dashboard/app/work/[id]/page.tsx`
- Create: `maintenance_os/dashboard/app/agents/page.tsx`
- Create: `maintenance_os/dashboard/app/approvals/page.tsx`
- Create: `maintenance_os/dashboard/app/activity/page.tsx`
- Create: `maintenance_os/dashboard/src/components/WorkItemTable.tsx`
- Create: `maintenance_os/dashboard/src/components/EvidencePanel.tsx`
- Create: `maintenance_os/dashboard/src/components/AgentRunPanel.tsx`
- Create: `maintenance_os/dashboard/src/components/ApprovalCard.tsx`
- Create: `maintenance_os/dashboard/src/components/ActivityTimeline.tsx`
- Create: `maintenance_os/dashboard/src/__tests__/work-item-detail.test.tsx`
- Create: `maintenance_os/dashboard/src/__tests__/approval.test.tsx`

**Step 1: Write failing work-item detail test**

Assert the page shows severity, confidence, source freshness, observed evidence, inferred hypotheses, claim owner, investigation progress, commands, test results, diff summary, and linked draft PR.

**Step 2: Implement queue and evidence views**

Filters cover state, severity, source, owner, and `needs approval`. Reprioritize and investigate commands include a generated idempotency key and disable while pending.

**Step 3: Write failing approval interaction test**

Assert the approval card displays the exact action, target SHA, evidence revision, expiration, and risk. Clicking approve posts those values and rejects a server response indicating stale evidence.

**Step 4: Implement approvals, agents, and activity views**

Never render a generic `Approve all`. Each approval is individual. The activity view shows timestamp, actor, action, target, result, and evidence link.

**Step 5: Run frontend suite**

Run:

```bash
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard type-check
```

Expected: PASS.

**Step 6: Commit**

```bash
git add maintenance_os/dashboard
git commit -m "feat(maintenance-os): add management workflows"
```

### Task 10: Add scheduling, recovery, and local startup

**Files:**
- Create: `maintenance_os/api/src/maintenance_os/services/scheduler.py`
- Create: `maintenance_os/api/src/maintenance_os/services/recovery.py`
- Create: `maintenance_os/api/tests/test_scheduler.py`
- Create: `maintenance_os/api/tests/test_recovery.py`
- Create: `maintenance_os/scripts/dev.sh`
- Create: `maintenance_os/.env.example`
- Create: `maintenance_os/README.md`

**Step 1: Write failing scheduler tests**

Use a fake clock. Prove manual refresh and scheduled refresh share one per-collector lock, repeated triggers coalesce, and read failures use bounded backoff without changing health to green.

**Step 2: Implement the conservative scheduler**

Schedule local Git every 60 seconds and GitHub/CI every 120 seconds. Use one in-process task registry. No job survives as an untracked background coroutine; startup and shutdown own all tasks.

**Step 3: Write failing recovery tests**

Seed a running investigation with a dead PID, expired claim, and retained worktree. Assert startup marks it blocked, records a recovery audit event, releases the claim, and keeps the evidence/worktree.

**Step 4: Implement recovery and startup wiring**

FastAPI lifespan initializes SQLite/WAL, runs migrations, reconciles interrupted work, starts collectors, and stops tasks on shutdown.

**Step 5: Add local startup script and documentation**

`maintenance_os/scripts/dev.sh` validates the configured repository, binds API/dashboard to localhost, starts both processes, forwards termination, and never kills unrelated processes. Document environment variables and credential prerequisites.

**Step 6: Run backend suite and shell check**

Run:

```bash
cd maintenance_os/api && uv run pytest -v
bash -n maintenance_os/scripts/dev.sh
```

Expected: PASS.

**Step 7: Commit**

```bash
git add maintenance_os
git commit -m "feat(maintenance-os): add scheduling and recovery"
```

### Task 11: Prove the end-to-end safety contract

**Files:**
- Create: `maintenance_os/e2e/package.json`
- Create: `maintenance_os/e2e/playwright.config.ts`
- Create: `maintenance_os/e2e/tests/failing-test-to-draft-pr.spec.ts`
- Create: `maintenance_os/api/tests/acceptance/test_draft_pr_boundary.py`
- Modify: `pnpm-workspace.yaml`
- Modify: `pnpm-lock.yaml`
- Modify: `maintenance_os/README.md`

**Step 1: Write the failing backend acceptance test**

Create a temporary bare remote and working repository with a deliberately failing test. Feed a matching CI-failure signal, run a fake agent that fixes the test and commits, create a fake draft PR, and assert:

```python
assert work_item.state is WorkItemState.WAITING_APPROVAL
assert change.is_draft is True
assert change.tests_passed is True
assert fake_github.merge_calls == []
assert audit_log.contains("draft_pr_created")
assert audit_log.contains("approval_requested")
```

**Step 2: Run and verify failure**

Run: `cd maintenance_os/api && uv run pytest tests/acceptance/test_draft_pr_boundary.py -v`

Expected: FAIL until the vertical slice is fully wired.

**Step 3: Wire the acceptance path**

Connect collection, reconciliation, queue dispatch, claim acquisition, agent runner, test evidence, draft-PR adapter, state transition, and approval request. Keep merge outside this path.

**Step 4: Add the Playwright scenario**

The browser test opens Today, selects the CI failure, starts investigation, observes progress, opens evidence, sees the draft PR, and confirms the merge action is represented only as a pending approval.

**Step 5: Run all focused verification**

Run:

```bash
cd maintenance_os/api && uv run pytest -v
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard type-check
corepack pnpm@10.18.2 --filter @nous/maintenance-e2e test
git diff --check origin/develop...HEAD
```

Expected: all tests PASS and `git diff --check` emits no output.

**Step 6: Commit**

```bash
git add maintenance_os pnpm-workspace.yaml pnpm-lock.yaml
git commit -m "test(maintenance-os): prove draft-PR approval boundary"
```

### Task 12: Final review and handoff

**Files:**
- Modify if needed: `docs/plans/2026-07-11-project-maintenance-os-design.md`
- Modify if needed: `docs/plans/2026-07-11-project-maintenance-os.md`
- Modify if needed: `maintenance_os/README.md`

**Step 1: Verify the implementation against the approved design**

Check every MVP item, safety rule, deferred item, and success criterion. Record any deliberate deviation in the README and design document before review.

**Step 2: Run the complete maintenance-OS verification set**

```bash
cd maintenance_os/api && uv run pytest -v
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard test
corepack pnpm@10.18.2 --filter @nous/maintenance-dashboard type-check
corepack pnpm@10.18.2 --filter @nous/maintenance-e2e test
git status --short
git diff --check origin/develop...HEAD
```

Expected: all tests PASS; only intentional files are changed; diff check is clean.

**Step 3: Perform a safety-focused code review**

Review subprocess construction, path containment, secret redaction, approval freshness, idempotency, SQLite transaction boundaries, claim expiration, stale collector behavior, and draft-versus-merge enforcement. Resolve every high-confidence finding with a failing test first.

**Step 4: Commit final documentation corrections**

```bash
git add docs/plans maintenance_os
git commit -m "docs(maintenance-os): finalize local MVP handoff"
```

**Step 5: Prepare a draft pull request**

The pull request must summarize the architecture, local startup, verification commands, safety boundary, deferred integrations, and the end-to-end acceptance result. Keep it draft until the operator reviews the local dashboard.
