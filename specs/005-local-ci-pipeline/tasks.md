# Tasks: Local CI Pipeline Runner

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Task Legend

- `[P]` = Can run in parallel with other [P] tasks in same phase
- `[S]` = Shell/Script task
- `[US#]` = User Story reference

## Phase 1: Setup & Utilities

> Shared infrastructure required by all user stories.

- [x] **T001** [S] Create `scripts/ci/utils.sh` — Color constants (GREEN, RED, YELLOW, CYAN, RESET) with NO_COLOR/non-tty detection; `format_duration()` to convert seconds to `Xm Ys` format; `check_prereqs()` that sets HAS_DOCKER, HAS_NODE, HAS_PYTHON, HAS_GIT flags via `command -v`; `print_header()` and `print_separator()` for box-drawing output.
  - **File**: `scripts/ci/utils.sh`
  - **Refs**: plan.md § Prerequisite Checks, § Color and Formatting; research.md R4, R5

- [x] **T002** [S] Create `run-ci.sh` entry point — Shebang (`#!/usr/bin/env bash`), `set -uo pipefail` (no `-e`, we handle errors manually), auto-detect project root via `git rev-parse --show-toplevel`, `cd` to it, source `scripts/ci/utils.sh` and `scripts/ci/stages.sh`, call `check_prereqs`, declare `STAGE_RESULTS` and `STAGE_DURATIONS` associative arrays, declare `STAGE_ORDER` indexed array, define `run_stage()` wrapper that records start time, invokes the stage function, captures exit code + duration, stores in arrays. Add `print_summary()` that iterates arrays and prints the colorized table. Add `trap cleanup EXIT INT TERM`. Make executable (`chmod +x`).
  - **File**: `run-ci.sh`
  - **Depends on**: T001
  - **Refs**: plan.md § Architecture; research.md R2, R3; contracts/cli-interface.md

---

**CHECKPOINT**: After T001-T002, `./run-ci.sh` should run, detect prerequisites, print an empty summary, and exit 0.

## Phase 2: User Story 1 — Run Full CI Locally (P1)

> **Goal**: Developer runs `./run-ci.sh` with no arguments → all 5 fast stages execute sequentially → colorized summary with pass/fail/skip and timing → non-zero exit on any failure.
>
> **Independent test**: Run `./run-ci.sh` from project root. Verify lint-backend, lint-frontend, unit-tests, security-scan, frontend-tests all execute. Verify summary table shows status + duration for each. Verify exit code is 1 if any stage fails, 0 if all pass.

- [x] **T003** [S] [US1] Create `scripts/ci/stages.sh` with `stage_lint_backend()` — Build Docker lint image (`docker build -t rag-lint:ci -f backend/docker/Dockerfile.lint .`), run ruff (`docker run --rm rag-lint:ci ruff check backend/src`). Note: black/isort/mypy have `continue-on-error` in CI, so run them but don't count their failure as stage failure (capture output, warn if they fail, but return the ruff exit code).
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (lint-backend row); `.github/workflows/test-pipeline.yml` lines 47-69

- [x] **T004** [S] [P] [US1] Add `stage_lint_frontend()` to stages.sh — `cd frontend && npm ci && npm run type-check && npm run lint`. lint has `continue-on-error` in CI, so warn on lint failure but only fail on type-check failure.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (lint-frontend row); test-pipeline.yml lines 71-95

- [x] **T005** [S] [P] [US1] Add `stage_unit_tests()` to stages.sh — Install pytest dependencies if not present (`pip install pytest pytest-asyncio pytest-cov pytest-xdist`), install backend requirements (`pip install --build-constraint backend/constraints-ci.txt -r backend/requirements.txt`), run `pytest backend/tests/ -c backend/pytest.ini -m "unit or not (integration or e2e or slow)" --cov=backend/src --cov-report=term-missing -v` with `ENVIRONMENT=testing DATABASE_URL=sqlite:///:memory:`.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (unit-tests row); test-pipeline.yml lines 100-158

- [x] **T006** [S] [P] [US1] Add `stage_security_scan()` to stages.sh — Install `bandit safety` if not present, run `bandit -r backend/src -ll -ii -x tests` (continue-on-error in CI, so warn but don't fail), run `safety check -r backend/requirements.txt` (also continue-on-error).
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (security-scan row); test-pipeline.yml lines 163-184

- [x] **T007** [S] [P] [US1] Add `stage_frontend_tests()` to stages.sh — `cd frontend && npm ci && CI=true npm test -- --coverage --watchAll=false`.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (frontend-tests row); test-pipeline.yml lines 189-219

- [x] **T008** [S] [US1] Wire stage registry in `run-ci.sh` — Define `ALL_STAGES` ordered array with stage names, `STAGE_PREREQS` associative array mapping each stage to its required tools, `STAGE_FUNCTIONS` mapping each stage name to its function. In the main flow: if no CLI args, set `SELECTED_STAGES=ALL_STAGES`; iterate selected stages, check prereqs, call `run_stage` or skip. At end call `print_summary` and exit with overall result.
  - **File**: `run-ci.sh`
  - **Depends on**: T003, T004, T005, T006, T007
  - **Refs**: plan.md § Default Stage Order, § Architecture

- [x] **T009** [S] [US1] Add `--quick` mode to arg parsing in `run-ci.sh` — When `--quick` is passed, set `SELECTED_STAGES=(lint-backend lint-frontend)` instead of all stages. Satisfies FR-007.
  - **File**: `run-ci.sh`
  - **Depends on**: T008
  - **Refs**: plan.md § CLI Interface; spec.md FR-007

---

**CHECKPOINT**: After T003-T009, `./run-ci.sh` runs all 5 fast stages end-to-end, `./run-ci.sh --quick` runs only lints, summary table is displayed, exit code reflects results. US1 acceptance scenarios 1-3 satisfied.

## Phase 3: User Story 2 — Run Individual Stages (P1)

> **Goal**: Developer runs `./run-ci.sh lint-frontend frontend-tests` → only those stages run in canonical order → summary shows only executed stages.
>
> **Independent test**: Run `./run-ci.sh frontend-tests`. Verify only frontend-tests executes. Run `./run-ci.sh lint-backend unit-tests`. Verify both run in correct order (lint-backend first).

- [x] **T010** [S] [US2] Add positional stage selection to arg parsing in `run-ci.sh` — Parse non-flag arguments as stage names, validate each against `ALL_STAGES`, error with exit code 2 if unknown stage name. Filter and reorder selected stages to match canonical `ALL_STAGES` order. Add `--backend` shortcut (lint-backend, unit-tests, security-scan, resilience-tests), `--frontend` shortcut (lint-frontend, frontend-tests), `--e2e` shortcut (e2e-tests).
  - **File**: `run-ci.sh`
  - **Depends on**: T008
  - **Refs**: plan.md § CLI Interface; spec.md FR-002; contracts/cli-interface.md

---

**CHECKPOINT**: After T010, `./run-ci.sh lint-backend unit-tests` runs only those two stages. `./run-ci.sh --backend` runs backend group. Unknown stage names produce error with exit 2. US2 acceptance scenarios 1-2 satisfied.

## Phase 4: User Story 3 — Docker E2E Tests Locally (P2)

> **Goal**: Developer runs `./run-ci.sh --e2e` → backend/frontend Docker images built → Postgres/Redis started → smoke tests run → all containers cleaned up.
>
> **Independent test**: Run `./run-ci.sh --e2e`. Verify Docker images are built, services start, smoke tests execute, and `docker ps` shows no orphaned containers after completion. Run with Docker stopped: verify clear error message and stage skipped.

- [x] **T011** [S] [US3] Add `stage_integration_tests()` to stages.sh — Start Postgres and Redis via `docker compose -p rag_local_ci -f docker-compose.ci.yml up -d postgres redis`, wait for healthy, run `pytest backend/tests/integration/ -c backend/pytest.ini -m integration -v` with `DATABASE_URL=postgresql://test:test@localhost:5432/test_db REDIS_URL=redis://localhost:6379/0 ENVIRONMENT=testing`. Handle exit code 5 (no tests) as success.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (integration-tests); test-pipeline.yml lines 224-306

- [x] **T012** [S] [P] [US3] Add `stage_resilience_tests()` to stages.sh — `pytest backend/tests/ -c backend/pytest.ini -m resilience -v` with `ENVIRONMENT=testing DATABASE_URL=sqlite:///:memory:`. Handle exit code 5 as success.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (resilience-tests); test-pipeline.yml lines 311-367

- [x] **T013** [S] [P] [US3] Add `stage_api_contract_tests()` to stages.sh — Start Postgres via `docker compose -p rag_local_ci -f docker-compose.ci.yml up -d postgres`, wait for healthy, install `schemathesis`, run `pytest backend/tests/api_contract/ -c backend/pytest.ini -v` with `DATABASE_URL=postgresql://test:test@localhost:5432/test_db ENVIRONMENT=testing`.
  - **File**: `scripts/ci/stages.sh`
  - **Refs**: plan.md § Stage Mapping (api-contract-tests); test-pipeline.yml lines 372-419

- [x] **T014** [S] [US3] Add `stage_e2e_tests()` to stages.sh — Build backend image (`docker build --build-arg PYTHON_VERSION=3.11 --build-arg TORCH_CPU_ONLY=true -t rag-backend:test -f backend/docker/Dockerfile.prod .`), build frontend image (`docker build -t rag-frontend:test -f frontend/Dockerfile.prod .`), start Postgres/Redis via compose, start backend/frontend containers (with `--name backend-local-ci`/`frontend-local-ci` and `--network rag_local_ci_ci-network`), wait for health, run smoke tests via compose, cleanup containers.
  - **File**: `scripts/ci/stages.sh`
  - **Depends on**: T011 (shares compose infrastructure pattern)
  - **Refs**: plan.md § Stage Mapping (e2e-tests); test-pipeline.yml lines 424-548; docker-compose.ci.yml

- [x] **T015** [S] [US3] Update stage registry and cleanup in `run-ci.sh` — Add integration-tests, resilience-tests, api-contract-tests, e2e-tests to `ALL_STAGES`, `STAGE_PREREQS`, and `STAGE_FUNCTIONS`. Update `cleanup()` to stop `rag_local_ci` compose project and named containers. Ensure cleanup runs on EXIT/INT/TERM.
  - **File**: `run-ci.sh`
  - **Depends on**: T011, T012, T013, T014
  - **Refs**: plan.md § Cleanup & Signal Handling; spec.md FR-004

---

**CHECKPOINT**: After T011-T015, `./run-ci.sh --e2e` builds images, starts services, runs smoke tests, and cleans up. `./run-ci.sh` now runs all 9 stages. Docker cleanup verified via `docker ps` after run. US3 acceptance scenarios 1-2 satisfied.

## Phase 5: User Story 4 — Smart Change Detection (P3)

> **Goal**: Developer runs `./run-ci.sh --auto` → git diff detects changed files → only relevant stages run.
>
> **Independent test**: Make changes only in `frontend/`, run `./run-ci.sh --auto`, verify only frontend stages run. Make changes in both `backend/` and `frontend/`, verify both groups run.

- [x] **T016** [S] [US4] Create `scripts/ci/detect-changes.sh` — Function `detect_changed_stages()` that runs `git diff --name-only develop...HEAD` (fallback to `main...HEAD`), categorizes files by path prefix (backend/tests → backend_changed, frontend → frontend_changed, Dockerfile/docker-compose → docker_changed, .github → ci_changed), returns appropriate stage list: if docker/ci changed → all stages; if only backend → backend group; if only frontend → frontend group; if both → all except e2e.
  - **File**: `scripts/ci/detect-changes.sh`
  - **Refs**: plan.md § Change Detection Logic; spec.md FR-009

- [x] **T017** [S] [US4] Wire `--auto` flag in `run-ci.sh` — Source `scripts/ci/detect-changes.sh`, when `--auto` passed call `detect_changed_stages()` and use returned list as `SELECTED_STAGES`. Require git (check HAS_GIT), error if not available.
  - **File**: `run-ci.sh`
  - **Depends on**: T016
  - **Refs**: plan.md § CLI Interface; spec.md FR-009

---

**CHECKPOINT**: After T016-T017, `./run-ci.sh --auto` auto-detects changes and selects stages. US4 acceptance scenarios 1-2 satisfied.

## Phase 6: Polish & Cross-Cutting

- [x] **T018** [S] Add `--help` output to `run-ci.sh` — Print usage, available stages with descriptions, available options, examples. Exit 0 after printing help.
  - **File**: `run-ci.sh`
  - **Refs**: contracts/cli-interface.md; spec.md FR-008

- [x] **T019** [S] [P] Add project root auto-detection — In `run-ci.sh`, before sourcing helpers, if not in project root, detect via `git rev-parse --show-toplevel` and `cd` to it. Print note about detected root. Satisfies FR-008.
  - **File**: `run-ci.sh`
  - **Refs**: spec.md FR-008; edge case "invoked from subdirectory"

- [x] **T020** [S] [P] Add stale container cleanup on startup — In `run-ci.sh`, before running stages, check for existing `rag_local_ci` containers or `backend-local-ci`/`frontend-local-ci` containers. If found, warn and clean them up.
  - **File**: `run-ci.sh`
  - **Refs**: spec.md edge case "database container from previous failed run"

---

**CHECKPOINT**: All functional requirements (FR-001 through FR-011) satisfied. All user stories complete.

## Dependency Graph

```
T001 ──→ T002 ──→ T003 ──┐
                   T004 ──┤ (T003-T007 are [P] — different functions in same file,
                   T005 ──┤  but same file so write sequentially)
                   T006 ──┤
                   T007 ──┘──→ T008 ──→ T009 (US1 complete)
                                │
                                ├──→ T010 (US2 complete)
                                │
                                ├──→ T011 ──┐
                                │    T012 ──┤
                                │    T013 ──┘──→ T014 ──→ T015 (US3 complete)
                                │
                                ├──→ T016 ──→ T017 (US4 complete)
                                │
                                └──→ T018, T019, T020 [P] (Polish)
```

## Parallel Execution Examples

**Phase 2 (US1)**: T003-T007 add functions to the same file (`stages.sh`), so they must be written sequentially. However, T003-T007 are independent of T009, so T009 can be written immediately after T008 is complete while stages are being added.

**Phase 4 (US3)**: T011, T012, T013 add different stage functions and can be written in sequence within the same file, but T012 and T013 don't depend on T011's compose pattern (they use simpler setups).

**Phase 6 (Polish)**: T018, T019, T020 are independent and can be done in any order.

## Implementation Strategy

1. **MVP** = Phase 1 + Phase 2 (US1) — `./run-ci.sh` runs 5 fast stages with summary. Delivers immediate value.
2. **Increment 1** = Phase 3 (US2) — Stage selection. Small addition to arg parsing.
3. **Increment 2** = Phase 4 (US3) — Docker stages + E2E. Largest phase.
4. **Increment 3** = Phase 5 (US4) + Phase 6 — Smart detection + polish. Nice-to-haves.

## Completion Checklist

- [x] `./run-ci.sh` runs all 9 stages with colorized summary
- [x] `./run-ci.sh --quick` runs lint only
- [x] `./run-ci.sh lint-backend unit-tests` runs selected stages
- [x] `./run-ci.sh --backend` / `--frontend` / `--e2e` shortcuts work
- [x] `./run-ci.sh --auto` detects changes and selects stages
- [x] `./run-ci.sh --help` shows usage
- [x] Exit code 0 on all-pass, 1 on any failure, 2 on bad args
- [x] Docker cleanup verified (no orphaned containers after run)
- [x] Ctrl+C triggers cleanup
- [x] Works from subdirectory
- [x] Stale containers cleaned on startup
- [x] Script is executable (`chmod +x run-ci.sh`)
