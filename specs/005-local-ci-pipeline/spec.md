# Feature Specification: Local CI Pipeline Runner

**Created**: 2026-02-12
**Status**: Draft
**Priority**: P2

## Overview

Developers currently wait 15-30+ minutes for GitHub Actions CI feedback on each push. A local CI runner allows developers to execute the same checks locally before pushing, catching issues in seconds/minutes rather than waiting for remote CI. This reduces wasted CI minutes, speeds up iteration, and prevents the frustration of discovering lint or test failures after a push.

## Clarifications

### Session 2026-02-12

- Q: When a CI stage fails, should the runner stop immediately or continue running remaining stages? → A: Continue all — run remaining stages and report all failures at the end.

## User Scenarios & Testing

### User Story 1 - Run Full CI Locally Before Pushing (Priority: P1)

As a developer who has made changes across backend and frontend, I want to run the full CI pipeline locally so I can catch issues before pushing and waiting for remote CI.

**Why this priority**: This is the core use case — preventing wasted time and CI resources by catching issues early.

**Acceptance Scenarios**:

1. **Given** the developer is in the project root, **When** they run the local CI command with no arguments, **Then** all applicable CI stages run in sequence (lint, test, type-check, build) and report pass/fail for each stage.
2. **Given** the backend lint stage fails, **When** the remaining stages continue running, **Then** all stages execute to completion and the developer sees every failure in a single run, with clear indication of which stages failed.
3. **Given** all stages pass, **When** the full run completes, **Then** the developer sees a summary showing each stage's status, duration, and an overall pass/fail result.

---

### User Story 2 - Run Individual CI Stages (Priority: P1)

As a developer working only on the frontend, I want to run just the frontend-related CI checks without waiting for backend stages that my changes don't affect.

**Why this priority**: Most changes only affect one part of the system; running unrelated stages wastes time.

**Acceptance Scenarios**:

1. **Given** the developer specifies a single stage (e.g., "frontend-tests"), **When** the stage runs, **Then** only that stage executes and reports results.
2. **Given** the developer specifies multiple stages (e.g., "lint-frontend" and "frontend-tests"), **When** the stages run, **Then** only the specified stages execute in the correct order.

---

### User Story 3 - Run Docker-based E2E Tests Locally (Priority: P2)

As a developer who has changed Docker configuration or backend startup logic, I want to run the E2E smoke tests locally so I can verify Docker builds and service startup without pushing to CI.

**Why this priority**: E2E failures are the most expensive to debug remotely (long build times, opaque logs).

**Acceptance Scenarios**:

1. **Given** the developer requests E2E tests, **When** Docker and Docker Compose are available, **Then** the runner builds backend and frontend images, starts supporting services (PostgreSQL, Redis), runs smoke tests, and cleans up all containers afterward.
2. **Given** Docker is not available, **When** the developer requests E2E tests, **Then** the runner clearly reports that Docker is required and skips the E2E stage.

---

### User Story 4 - Smart Stage Detection Based on Changed Files (Priority: P3)

As a developer who wants the fastest feedback loop, I want the runner to automatically detect which files I changed and only run relevant stages.

**Why this priority**: Nice-to-have optimization for experienced developers who want minimal friction.

**Acceptance Scenarios**:

1. **Given** the developer has only changed files under `frontend/`, **When** they run the local CI with auto-detection, **Then** only frontend-related stages run (lint-frontend, frontend-tests).
2. **Given** the developer has changed files in both `backend/` and `frontend/`, **When** they run with auto-detection, **Then** all relevant stages run.

---

### Edge Cases

- What happens when a required tool is missing (e.g., Docker, Node.js, Python)?
  - The runner reports which tools are missing and which stages are skipped, then runs the stages it can.
- What happens when the developer interrupts execution mid-run (Ctrl+C)?
  - The runner performs cleanup (stop Docker containers, remove temp files) before exiting.
- What happens when the database container from a previous failed run is still running?
  - The runner detects and cleans up stale containers before starting a new run.
- What happens when the runner is invoked from a subdirectory instead of the project root?
  - The runner auto-detects the project root (via git root or marker files) and operates from there.

## Requirements

### Functional Requirements

- **FR-001**: The runner MUST support executing all CI stages that the GitHub Actions pipeline runs: lint-backend, lint-frontend, unit-tests, frontend-tests, security-scan, integration-tests, resilience-tests, api-contract-tests, e2e-tests.
- **FR-002**: The runner MUST allow selecting individual stages or groups of stages to run.
- **FR-003**: The runner MUST display a clear summary after completion showing each stage's pass/fail status, duration, and overall result.
- **FR-004**: The runner MUST clean up all resources (Docker containers, networks, temporary files) after completion, including on interruption or failure.
- **FR-005**: The runner MUST check for required dependencies (Docker, Node.js, Python, npm) before execution and report any missing prerequisites.
- **FR-006**: The runner MUST produce output that matches what developers would see in GitHub Actions, so failures can be understood and fixed locally.
- **FR-007**: The runner MUST support a "quick" mode that runs only fast checks (lint + type-check) for rapid pre-push validation.
- **FR-008**: The runner MUST be invocable from any directory within the project (auto-detecting project root).
- **FR-009**: The runner SHOULD support auto-detecting changed files and running only relevant stages.
- **FR-010**: The runner MUST exit with a non-zero exit code if any stage fails, making it suitable for use in git pre-push hooks.
- **FR-011**: The runner MUST continue executing remaining stages after a stage failure (continue-all behavior), collecting and reporting all failures in the final summary.

## Success Criteria

- **SC-001**: Developers can run the full local CI pipeline and get results within 10 minutes on a standard development machine (compared to 15-30 minutes waiting for remote CI).
- **SC-002**: At least 90% of CI failures that would occur remotely are caught locally before pushing.
- **SC-003**: Running quick-mode checks (lint + type-check) completes in under 2 minutes.
- **SC-004**: Developers report at least 50% reduction in "push, wait for CI, fix, push again" cycles.
- **SC-005**: The runner can be used by a new team member in under 5 minutes with no manual setup beyond running the command.
- **SC-006**: All Docker resources are fully cleaned up after every run (no orphaned containers or networks).

## Assumptions

- Developers have Docker and Docker Compose installed for E2E stages (standard for this project).
- Node.js 20 and Python 3.11 are available in the developer's environment.
- The local CI runner is a shell script (bash) for maximum portability and minimal dependencies, consistent with the existing project tooling.
- Performance tests are excluded from local CI by default (they require dedicated infrastructure).
- The runner uses the same Docker images and commands as the CI pipeline to ensure parity.

## Dependencies

- Existing GitHub Actions workflow definition (`.github/workflows/test-pipeline.yml`) as the source of truth for which stages to run and how.
- Docker Compose CI configuration (`docker-compose.ci.yml`) for E2E tests.
- Existing project tooling: `npm run lint`, `npm run test`, `npm run type-check`, `pytest`, `ruff`, `black`.

## Scope Boundaries

**In Scope**:

- Shell script runner for all CI stages
- Individual stage selection
- Quick-mode for fast pre-push checks
- E2E test support via Docker
- Auto-detection of changed files for smart stage selection
- Clean summary output
- Resource cleanup

**Out of Scope**:

- GUI or web dashboard for CI results
- Parallel stage execution (stages run sequentially for simplicity and resource constraints)
- Remote CI triggering or monitoring
- Performance/load testing (requires dedicated infrastructure)
- Automatic fix/remediation of failures
- Integration with IDE plugins
