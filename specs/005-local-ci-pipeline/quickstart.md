# Quickstart: Local CI Pipeline Runner

## Prerequisites

- **Docker** + Docker Compose (for lint-backend, integration-tests, e2e-tests)
- **Node.js 20** + npm (for lint-frontend, frontend-tests)
- **Python 3.11** + pip (for unit-tests, security-scan, resilience-tests)
- **Git** (for --auto mode change detection)

## Quick Usage

```bash
# Run everything
./run-ci.sh

# Fast pre-push check (lint + type-check only, ~2 min)
./run-ci.sh --quick

# Backend changes only
./run-ci.sh --backend

# Frontend changes only
./run-ci.sh --frontend

# Run specific stages
./run-ci.sh lint-backend unit-tests

# E2E smoke tests (Docker full stack)
./run-ci.sh --e2e

# Auto-detect what changed and run relevant stages
./run-ci.sh --auto
```

## What It Runs

The script mirrors the GitHub Actions CI pipeline locally:

1. **lint-backend** — Ruff, Black, isort, MyPy (via Docker)
2. **lint-frontend** — TypeScript type-check + ESLint
3. **unit-tests** — Backend pytest unit tests
4. **security-scan** — Bandit + Safety
5. **frontend-tests** — Jest tests with coverage
6. **resilience-tests** — Backend resilience tests
7. **integration-tests** — Backend integration tests (Docker Postgres/Redis)
8. **api-contract-tests** — API contract validation (Docker Postgres)
9. **e2e-tests** — Full Docker build + Playwright smoke tests

## Behavior

- **Continue-all**: All stages run even if earlier ones fail
- **Summary**: Colorized pass/fail/skip table with timing at the end
- **Cleanup**: Docker containers are cleaned up automatically, even on Ctrl+C
- **Exit code**: 0 if all pass, 1 if any fail (suitable for git hooks)
