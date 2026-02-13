# CLI Contract: run-ci.sh

**Date**: 2026-02-12

## Usage

```
./run-ci.sh [OPTIONS] [STAGE...]
```

## Options

| Option       | Description                                                                   |
| ------------ | ----------------------------------------------------------------------------- |
| `--help`     | Show help text and available stages                                           |
| `--quick`    | Run only fast checks: lint-backend, lint-frontend                             |
| `--backend`  | Run backend stages: lint-backend, unit-tests, security-scan, resilience-tests |
| `--frontend` | Run frontend stages: lint-frontend, frontend-tests                            |
| `--e2e`      | Run E2E tests (Docker full stack build + smoke tests)                         |
| `--auto`     | Auto-detect changed files and run relevant stages                             |

## Positional Arguments

Zero or more stage names from the available stages list. When provided, only those stages run (in the canonical order).

## Available Stages

| Stage Name           | Description                                              |
| -------------------- | -------------------------------------------------------- |
| `lint-backend`       | Build lint Docker image, run ruff + black + isort + mypy |
| `lint-frontend`      | npm ci + type-check + lint                               |
| `unit-tests`         | pytest unit tests with coverage                          |
| `security-scan`      | bandit + safety                                          |
| `frontend-tests`     | Jest tests with coverage                                 |
| `resilience-tests`   | pytest resilience tests                                  |
| `integration-tests`  | Docker Postgres/Redis + pytest integration tests         |
| `api-contract-tests` | Docker Postgres + schemathesis/pytest contract tests     |
| `e2e-tests`          | Full Docker build + compose up + Playwright smoke tests  |

## Exit Codes

| Code | Meaning                          |
| ---- | -------------------------------- |
| 0    | All executed stages passed       |
| 1    | One or more stages failed        |
| 2    | Invalid arguments or usage error |

## Environment Variables

| Variable   | Default   | Description                                            |
| ---------- | --------- | ------------------------------------------------------ |
| `NO_COLOR` | _(unset)_ | When set, disables colorized output                    |
| `CI`       | _(unset)_ | When set, disables colorized output (CI compatibility) |

## Output

- Each stage prints its name and real-time output to stdout
- After all stages complete, a summary table is printed showing pass/fail/skip status and duration for each stage
- Total execution time is reported
- Overall PASSED/FAILED status is reported
