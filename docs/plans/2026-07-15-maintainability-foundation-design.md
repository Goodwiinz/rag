# Maintainability Foundation and Pilot Refactors Design

**Date:** 2026-07-15

**Status:** Approved

## Purpose

Establish one enforceable maintenance baseline for the NOUS FastAPI and Next.js codebase, then prove the baseline through two behavior-preserving pilot refactors: the backend workspace API and the frontend chat surface.

The work addresses recurring NOUS failure patterns documented in the project wiki: transaction-ordering errors, async-session misuse, tenant-scope omissions, competing persistence paths, tests that do not exercise their claimed race, package-manager drift, and conclusions drawn from stale artifacts.

## Current `origin/develop` Prerequisites

The current base already contains two pieces that were missing from the older audit checkout:

- PR #1152 removed the false `api-contract-tests` lane and added a regression test preventing its return.
- PR #1163 added deterministic FastAPI OpenAPI generation, committed TypeScript output, a blocking schema-drift job, and one adopt-on-touch frontend consumer.

The implementation therefore extends and adopts those mechanisms. It does not recreate them. In particular, contract work focuses on verifying TypeScript-generation drift in CI and migrating the workspace/chat pilot types onto the existing generated contract.

## Goals

- Make local development, CI, and documentation use the same package manager, runtime versions, and validation commands.
- Replace advisory or bypassable checks with gradual quality ratchets that reject new debt without requiring a whole-codebase cleanup.
- Make FastAPI OpenAPI the authoritative frontend HTTP contract.
- Preserve one canonical writer for persisted chat state.
- Give backend services explicit ownership of business rules and transactions.
- Prove the standards on one large backend router and one large frontend route/store surface.
- Keep every change independently reviewable, deployable, and reversible.

## Non-goals

- A whole-codebase rewrite or directory reorganization.
- Product behavior, endpoint, response-shape, or visual-design changes.
- A generic repository abstraction around every SQLAlchemy query.
- Replacing TanStack Query, Zustand, Celery, SQLAlchemy, Vitest, or Playwright.
- Raising global coverage to an arbitrary target in one change.
- Removing legacy compatibility code before callers and regression tests prove it is unused.

## Approaches Considered

### Foundation only

This is the lowest-risk option, but it leaves the largest architectural hotspots untouched and does not prove that the standards work on real code.

### One modernization PR

This minimizes calendar time but combines tool upgrades, CI behavior, API contracts, backend transactions, and frontend streaming into one difficult-to-review rollback unit.

### Staged foundation plus pilots

This is the selected approach. A sequence of independently mergeable PRs establishes the baseline before applying it to the workspace and chat features. Each PR has a narrow purpose, focused verification, and an explicit rollback boundary.

## PR Sequence

1. Toolchain consistency
2. Quality-gate ratchets
3. Generated-contract adoption and TypeScript drift enforcement
4. Backend workspace pilot
5. Frontend chat pilot
6. Engineering standards and architectural regression checks

Later PRs build on earlier contracts, but every merged state remains runnable and deployable.

## Toolchain Consistency

The repository will have one declared frontend package manager and runtime matrix:

- pnpm is used in root scripts, frontend scripts, documentation, CI, and container builds.
- The Node version agrees across `.nvmrc`, package `engines`, CI, and active Docker build paths.
- Next.js, React, React DOM, ESLint, and `eslint-config-next` use compatible versions.
- Local and CI validation invoke the same repository-owned commands.
- Pre-commit and CI use the same pinned Python formatter, linter, and type-checker versions.

Documentation will describe commands that actually exist and run in the active workflow. Stale historical reports are not rewritten unless they are presented as current instructions.

## Quality Ratchets

The migration must reject new debt without pretending the existing tree is clean.

- Capture the current lint, type, and coverage baselines before changing enforcement.
- New or touched code cannot introduce ignored undefined-name, async, import, or type errors.
- Existing exclusions remain explicit and shrink when files are touched.
- Each exclusion has a removal condition; exclusions are not silently expanded.
- Frontend coverage is raised through a ratchet, not a one-time global target.
- CI jobs may be advisory only when their summary labels them advisory. A missing or non-blocking test suite cannot appear as a required contract gate.

## API Contract Architecture

FastAPI Pydantic request and response models remain the source of truth.

```text
Pydantic models
  -> deterministic OpenAPI document
  -> generated TypeScript definitions
  -> typed frontend client boundary
  -> TanStack Query or streaming adapter
```

CI generates the OpenAPI document and TypeScript output, then fails if the committed artifacts differ. Generated definitions are not manually edited.

Handwritten TypeScript types remain appropriate for frontend-only presentation and state-machine concepts. Zod remains at untrusted runtime boundaries, including SSE frames and third-party payloads; it should not duplicate every generated HTTP interface.

## Backend Boundaries

The workspace pilot retains all existing endpoints and wire formats while separating responsibilities:

```text
HTTP request
  -> resource router
  -> feature service
  -> tenant-scoped repository or query helper
  -> SQLAlchemy session
  -> Pydantic response
```

- Routers own FastAPI dependencies, parameter parsing, status codes, and response models.
- Services own authorization orchestration, business rules, transaction boundaries, and side-effect ordering.
- Repositories or query helpers own reusable persistence queries and require scope arguments.
- One `AsyncSession` belongs to one request or concurrent task.
- Durable or long-running work remains in Celery.

The current workspace surface is divided by resource: workspaces, members, conversations, threads, messages, and collections. Extraction happens behind the existing router exports so application registration and public URLs remain stable.

## Frontend Boundaries

The chat page becomes a composition root rather than a second application layer.

- TanStack Query owns request-backed server state.
- The streaming adapter/store owns active SSE and HITL state.
- Zustand owns genuinely cross-component client UI state.
- React component state owns local presentation state.
- The backend remains the canonical persisted-chat writer.

Command execution, project context, citations, transcript coordination, and streaming lifecycle move into focused feature modules. The refactor does not introduce a second persistence path or reimplement the confirmation stream.

## Failure Handling

### Backend

- Tenant and ownership checks fail closed before resource reads or mutations.
- Services explicitly commit or roll back transactions; routers do not commit.
- Remote storage or external-service operations use compensation when they cannot share the database transaction.
- Background work is enqueued only after authoritative state commits, or through an outbox-equivalent mechanism when required.
- Existing structured error responses and correlation identifiers remain intact.
- Scope-requiring query helpers cannot silently fall back to a global query.

### Frontend

- Streaming frames remain transient until the backend terminal event confirms authoritative state.
- Thread changes invalidate previous asynchronous work with stable request or epoch identities.
- HITL confirmation remains idempotent.
- Loading, empty, partial, retryable, and terminal-error states remain distinct.
- Compatibility adapters stay in place until all callers migrate and tests prove the new path is authoritative.

## Verification

### Foundation

- Backend: Ruff, format check, MyPy, focused pytest, then the full unit lane.
- Frontend: ESLint, TypeScript, focused Vitest, then coverage.
- Contract: generate OpenAPI and TypeScript definitions, then require a clean diff.
- Local and CI commands use the same tool versions.

### Workspace pilot

Characterization and regression coverage must include:

- Endpoint paths, status codes, and response schemas.
- Owner, admin, member, and unauthorized behavior.
- Cross-organization denial.
- Soft-deleted membership restoration.
- Pagination and count-filter parity.
- Transaction rollback on failure.
- Session ownership for concurrent work.
- Background enqueue ordering where applicable.

### Chat pilot

Coverage must include:

- Cold initialization and first-message creation.
- Rapid thread switching and stale-response rejection.
- Pagination without transcript replacement.
- Streaming placeholder lifecycle.
- Stop, retry, and regeneration.
- HITL approve, reject, and error paths.
- Citation and project-context actions.
- Reload from server-canonical history.

Race and idempotency tests are mutation-verified: removing the target guard must make the test fail. Playwright remains focused on critical user journeys and uses accessible locators and web-first assertions.

## Rollback and Delivery

- Each PR is independently reversible.
- Tool upgrades are isolated from architectural refactors.
- Structural moves retain compatibility exports until callers migrate.
- Compatibility code is removed only in a later commit after focused and mutation verification.
- No PR combines broad dependency upgrades with business-logic movement.
- Deployment behavior is judged only after verifying checkout, artifact, runtime, and test-medium identity.

## Completion Criteria

- Runtime, package-manager, and framework versions agree across active surfaces.
- No active CI job references a missing suite or reports an advisory lane as blocking.
- New and touched code cannot bypass lint or type checks.
- Frontend HTTP types regenerate deterministically from FastAPI.
- Workspace routers contain transport concerns rather than transaction logic.
- Chat persistence retains one canonical writer and one terminal reconciliation path.
- Pilot mutation tests kill the guards they claim to exercise.
- Current documentation matches the commands CI runs.
- Every PR is green, deployable, and independently revertible.
