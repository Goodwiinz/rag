# Research: Local CI Pipeline Runner

**Date**: 2026-02-12

## R1: Bash Script Architecture for Multi-Stage Runners

**Decision**: Single entry-point script sourcing modular helper files via `source`/`.`

**Rationale**: Keeps the main script small and readable while allowing each stage to be defined as an independent function. Sourcing (not subshelling) preserves shared state (arrays for results tracking, color variables).

**Alternatives considered**:

- Makefile-based (rejected: poor error handling, no built-in timing, unfriendly output)
- Python script (rejected: adds dependency, overkill for wrapping shell commands)
- `act` (GitHub Actions local runner) (rejected: slow, heavy Docker usage, imperfect CI environment replication, not all GitHub Actions features supported)

## R2: Continue-All Failure Behavior Pattern

**Decision**: Track exit codes in an associative array, continue execution, report all failures in final summary.

**Rationale**: Bash associative arrays (`declare -A`) map stage names to exit codes cleanly. After each stage, store the result and continue. At summary time, iterate the array to build the output table.

**Alternatives considered**:

- `set -e` with trap (rejected: stops on first failure, contradicts spec requirement FR-011)
- Subshell per stage with separate tracking (rejected: unnecessary complexity, loses shared state)

## R3: Docker Cleanup Strategy

**Decision**: `trap cleanup EXIT INT TERM` with a cleanup function that stops/removes named containers and runs `docker compose down -v --remove-orphans`.

**Rationale**: The EXIT trap ensures cleanup runs regardless of how the script exits (success, failure, signal). Using a distinct project name (`rag_local_ci`) avoids conflicts with the developer's running `docker-compose.development.yml` stack.

**Alternatives considered**:

- Cleanup only on failure (rejected: orphaned containers from successful runs still waste resources)
- No automatic cleanup, require manual (rejected: violates FR-004 and SC-006)

## R4: Stage Prerequisite Detection

**Decision**: `command -v <tool>` checks at startup, populating a `HAS_DOCKER`, `HAS_NODE`, `HAS_PYTHON` set of flags. Each stage function checks its required flags before executing.

**Rationale**: `command -v` is POSIX-compliant and works across bash/zsh. Checking once at startup avoids repeated checks. Missing prerequisites skip the stage with a warning rather than failing the entire run.

**Alternatives considered**:

- `which` (rejected: not POSIX, behaves differently across systems)
- Check per-stage (rejected: redundant, slower)

## R5: Color and Formatting

**Decision**: ANSI escape codes with `tput` fallback, disabled when `NO_COLOR` env var is set or stdout is not a terminal.

**Rationale**: Follows the [NO_COLOR standard](https://no-color.org/) for accessibility. ANSI codes work in all modern terminals. `tput` provides graceful degradation.

**Alternatives considered**:

- Always colorize (rejected: breaks piped output and accessibility)
- No color (rejected: harder to scan results visually)

## R6: Integration Tests Service Management

**Decision**: Use `docker compose` with the existing `docker-compose.ci.yml` for Postgres/Redis, but with a distinct project name (`rag_local_ci`) to avoid conflicts with the development stack.

**Rationale**: The CI compose file already defines the correct services, healthchecks, and network configuration. Using a different project name ensures the local CI runner doesn't interfere with `docker-compose.development.yml` containers that may be running on different ports.

**Alternatives considered**:

- Start Postgres/Redis natively (rejected: inconsistent with CI, requires local installation)
- Use testcontainers (rejected: only works within pytest, not from bash)
