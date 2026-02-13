# Implementation Plan: Local CI Pipeline Runner

**Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)

## Summary

A single bash script (`run-ci.sh`) at the project root that mirrors the GitHub Actions test pipeline locally. Developers can run all CI stages or select individual ones, with continue-all failure behavior, colorized summary output, Docker cleanup, and smart changed-file detection. No new backend/frontend code — this is a pure developer-tooling feature.

## Technical Context

**Runtime**: Bash 4+ (POSIX-compatible where possible)
**CI Source of Truth**: `.github/workflows/test-pipeline.yml` (11 jobs; 9 mapped to local stages — performance-tests excluded per spec, test-summary is CI-only)
**Docker**: Required for lint-backend, integration-tests, api-contract-tests, e2e-tests; optional for other stages
**Node.js**: Required for frontend stages (lint-frontend, frontend-tests)
**Python**: Required for backend stages (unit-tests, security-scan, integration-tests, resilience-tests, api-contract-tests)
**Key files**:

- `docker-compose.ci.yml` — E2E infrastructure (Postgres, Redis, backend, frontend, Playwright)
- `backend/docker/Dockerfile.lint` — Lightweight lint image (ruff, black, isort, mypy)
- `backend/docker/Dockerfile.prod` — Full backend image with TORCH_CPU_ONLY support
- `frontend/Dockerfile.prod` — Frontend production image
- `backend/constraints-ci.txt` — CI-specific pip constraints

## Constitution Check

| Principle                | Applicable? | Compliance                                                                             |
| ------------------------ | ----------- | -------------------------------------------------------------------------------------- |
| 0. Research-First        | No          | N/A — developer tooling, not research features                                         |
| I. Evaluation-First      | Yes         | Script itself tested via integration test; acceptance scenarios in spec define success |
| II. Modular Architecture | Yes         | Each stage is an independent function; stages composable via CLI args                  |
| III. Multi-Agent         | No          | N/A — no AI agents involved                                                            |
| IV. Hybrid Search        | No          | N/A — no search functionality                                                          |
| V. Enterprise Security   | No          | N/A — local dev tool, no auth/data concerns                                            |
| VI. Performance          | Yes         | Quick mode targets <2min; full run targets <10min (SC-001, SC-003)                     |
| VII. Observability       | Yes         | Colorized stage-by-stage output with timing; summary table at end                      |

No constitutional violations. The feature is developer tooling that supports the constitution's testing standards (comprehensive testing across all system layers) by making it faster to run those tests locally.

## Project Structure

### New Files

```
run-ci.sh                          # Main entry point (project root)
scripts/ci/                        # Stage implementation functions
├── stages.sh                      # Stage definitions (one function per CI job)
├── utils.sh                       # Shared utilities (colors, timing, prereq checks)
└── detect-changes.sh              # Git diff-based change detection
```

### No Changes Required

- No backend code changes
- No frontend code changes
- No database changes
- No API changes
- No UI changes

## Design

### Architecture

The script follows a simple pipeline pattern:

```
run-ci.sh (entry point)
  ├── Parse CLI arguments
  ├── Source scripts/ci/utils.sh (colors, timing, prereq checks)
  ├── Source scripts/ci/stages.sh (stage functions)
  ├── Check prerequisites (docker, node, python, npm, pip)
  ├── Resolve which stages to run:
  │   ├── No args → all stages (default order)
  │   ├── Named stages → only those
  │   ├── --quick → lint-backend + lint-frontend only
  │   ├── --auto → detect changed files → relevant stages
  │   └── --backend / --frontend → group shortcuts
  ├── Run stages sequentially (continue-all on failure)
  │   ├── For each stage: record start time, run, record exit code + duration
  │   └── Skip stages with missing prerequisites (warn, don't fail)
  ├── Cleanup (Docker containers, networks if E2E ran)
  └── Print summary table + exit with non-zero if any stage failed
```

### Stage Mapping (CI Job → Local Function)

| CI Job             | Local Stage Name     | Local Command                                                                                                         | Prerequisites                |
| ------------------ | -------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| lint-backend       | `lint-backend`       | `docker build + docker run` (ruff, black, isort, mypy)                                                                | Docker                       |
| lint-frontend      | `lint-frontend`      | `cd frontend && npm ci && npm run type-check && npm run lint`                                                         | Node.js, npm                 |
| unit-tests         | `unit-tests`         | `pytest backend/tests/ -m "unit or not (integration or e2e or slow)" -v`                                              | Python, pip                  |
| security-scan      | `security-scan`      | `bandit -r backend/src -ll -ii -x tests && safety check -r backend/requirements.txt`                                  | Python, pip                  |
| frontend-tests     | `frontend-tests`     | `cd frontend && npm ci && npm test -- --coverage --watchAll=false`                                                    | Node.js, npm                 |
| integration-tests  | `integration-tests`  | `docker compose -f docker-compose.ci.yml up -d postgres redis && pytest backend/tests/integration/ -m integration -v` | Docker, Python               |
| resilience-tests   | `resilience-tests`   | `pytest backend/tests/ -m resilience -v`                                                                              | Python, pip                  |
| api-contract-tests | `api-contract-tests` | `docker compose -f docker-compose.ci.yml up -d postgres && pytest backend/tests/api_contract/ -v`                     | Docker, Python               |
| e2e-tests          | `e2e-tests`          | `docker build images + docker compose up + smoke tests + cleanup`                                                     | Docker                       |
| performance-tests  | _(excluded)_         | N/A                                                                                                                   | Excluded per spec assumption |

### CLI Interface

```bash
# Run all stages (default)
./run-ci.sh

# Run specific stages
./run-ci.sh lint-backend unit-tests

# Group shortcuts
./run-ci.sh --quick        # lint-backend + lint-frontend (fast checks only)
./run-ci.sh --backend      # lint-backend + unit-tests + security-scan + resilience-tests
./run-ci.sh --frontend     # lint-frontend + frontend-tests
./run-ci.sh --e2e          # e2e-tests (Docker full stack)

# Smart detection
./run-ci.sh --auto         # Detect changed files, run relevant stages

# Help
./run-ci.sh --help
```

### Default Stage Order

Mirrors CI dependency graph (fast stages first):

1. `lint-backend`
2. `lint-frontend`
3. `unit-tests`
4. `security-scan`
5. `frontend-tests`
6. `resilience-tests`
7. `integration-tests`
8. `api-contract-tests`
9. `e2e-tests`

### Summary Output Format

```
══════════════════════════════════════════
  Local CI Pipeline Results
══════════════════════════════════════════
  ✓ lint-backend        [  32s]
  ✗ lint-frontend       [  18s]
  ✓ unit-tests          [ 4m12s]
  ✓ security-scan       [  15s]
  ✓ frontend-tests      [ 1m24s]
  - resilience-tests    [SKIPPED - no pytest]
  ✓ integration-tests   [ 3m02s]
  ✓ api-contract-tests  [ 2m15s]
  ✓ e2e-tests           [ 5m30s]
──────────────────────────────────────────
  FAILED (1 of 8 stages failed)
  Total time: 12m48s
══════════════════════════════════════════
```

### Change Detection Logic (--auto)

```bash
# Get changed files vs develop branch (or main if no develop)
changed_files=$(git diff --name-only develop...HEAD 2>/dev/null || git diff --name-only main...HEAD)

# Map paths to stages
backend_changed=false
frontend_changed=false
docker_changed=false
ci_changed=false

for file in $changed_files; do
  case "$file" in
    backend/*|tests/*)     backend_changed=true ;;
    frontend/*)            frontend_changed=true ;;
    *Dockerfile*|docker-*) docker_changed=true ;;
    .github/*)             ci_changed=true ;;
  esac
done

# Select stages based on what changed
# If ci_changed or docker_changed → run all
# If only backend → backend stages
# If only frontend → frontend stages
# If both → all non-e2e stages
```

### Cleanup & Signal Handling

```bash
cleanup() {
  echo "Cleaning up..."
  docker compose -p rag_local_ci -f docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true
  docker stop backend-local-ci frontend-local-ci 2>/dev/null || true
  docker rm backend-local-ci frontend-local-ci 2>/dev/null || true
}
trap cleanup EXIT INT TERM
```

### Prerequisite Checks

Before running any stages, verify tools exist:

- `docker` and `docker compose` — required for lint-backend, integration-tests, api-contract-tests, e2e-tests
- `node` and `npm` — required for lint-frontend, frontend-tests
- `python3` and `pip` — required for unit-tests, security-scan, resilience-tests, integration-tests, api-contract-tests
- `git` — required for --auto mode

Missing tools result in those stages being skipped with a warning, not a hard failure.

## Dependencies

- No new packages required
- Uses only existing project tooling and system utilities (bash, docker, node, python, git)

## Complexity Tracking

No constitutional violations or unusual complexity. This is a straightforward bash script that wraps existing CI commands.

## Implementation Phases

### Phase 1: Core Script + Fast Stages (P1)

- `run-ci.sh` entry point with arg parsing
- `scripts/ci/utils.sh` with colors, timing, prereq checks, summary output
- `scripts/ci/stages.sh` with lint-backend, lint-frontend, unit-tests, frontend-tests, security-scan
- `--quick` mode
- Continue-all failure behavior
- Non-zero exit code on failure

### Phase 2: Docker Stages + Groups (P1-P2)

- integration-tests, resilience-tests, api-contract-tests stages
- e2e-tests stage (full Docker build + compose up + smoke tests + cleanup)
- `--backend`, `--frontend`, `--e2e` group shortcuts
- Signal handling and Docker cleanup

### Phase 3: Smart Detection + Polish (P3)

- `scripts/ci/detect-changes.sh` with `--auto` mode
- `--help` output
- Project root auto-detection from subdirectories
