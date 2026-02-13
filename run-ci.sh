#!/usr/bin/env bash
# run-ci.sh — Local CI Pipeline Runner
# Mirrors the GitHub Actions test pipeline locally
# See: specs/005-local-ci-pipeline/ for full specification
set -uo pipefail

# ─── Project Root Detection ───────────────────────────────────────────────────

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$PROJECT_ROOT" ]]; then
    echo "ERROR: Not inside a git repository. Run from project root or a subdirectory."
    exit 2
fi

if [[ "$PWD" != "$PROJECT_ROOT" ]]; then
    echo "Note: Detected project root at $PROJECT_ROOT (running from subdirectory)"
    cd "$PROJECT_ROOT"
fi

# ─── Source Helpers ────────────────────────────────────────────────────────────

source scripts/ci/utils.sh
source scripts/ci/stages.sh
source scripts/ci/detect-changes.sh

# ─── Stage Registry ───────────────────────────────────────────────────────────

ALL_STAGES=(
    lint-backend
    lint-frontend
    unit-tests
    security-scan
    frontend-tests
    resilience-tests
    integration-tests
    api-contract-tests
    e2e-tests
)

declare -A STAGE_PREREQS=(
    [lint-backend]="docker"
    [lint-frontend]="node"
    [unit-tests]="python"
    [security-scan]="python"
    [frontend-tests]="node"
    [resilience-tests]="python"
    [integration-tests]="docker,python"
    [api-contract-tests]="docker,python"
    [e2e-tests]="docker"
)

declare -A STAGE_FUNCTIONS=(
    [lint-backend]=stage_lint_backend
    [lint-frontend]=stage_lint_frontend
    [unit-tests]=stage_unit_tests
    [security-scan]=stage_security_scan
    [frontend-tests]=stage_frontend_tests
    [resilience-tests]=stage_resilience_tests
    [integration-tests]=stage_integration_tests
    [api-contract-tests]=stage_api_contract_tests
    [e2e-tests]=stage_e2e_tests
)

declare -A STAGE_DESCRIPTIONS=(
    [lint-backend]="Build lint Docker image, run ruff + black + isort + mypy"
    [lint-frontend]="npm ci + type-check + lint"
    [unit-tests]="pytest unit tests with coverage"
    [security-scan]="bandit + safety"
    [frontend-tests]="Jest tests with coverage"
    [resilience-tests]="pytest resilience tests"
    [integration-tests]="Docker Postgres/Redis + pytest integration tests"
    [api-contract-tests]="Docker Postgres + schemathesis/pytest contract tests"
    [e2e-tests]="Full Docker build + compose up + Playwright smoke tests"
)

# ─── Result Tracking ──────────────────────────────────────────────────────────

declare -A STAGE_RESULTS    # stage_name → exit_code (0=pass, 1+=fail, -1=skipped)
declare -A STAGE_DURATIONS  # stage_name → duration_seconds
declare -a STAGE_ORDER      # ordered list of stage names that were executed

# ─── Cleanup ──────────────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo -e "${DIM}Cleaning up...${RESET}"
    docker compose -p rag_local_ci -f docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true
    docker stop backend-local-ci frontend-local-ci 2>/dev/null || true
    docker rm backend-local-ci frontend-local-ci 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# ─── Stale Container Cleanup ─────────────────────────────────────────────────

cleanup_stale() {
    local stale=false
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qE '^(backend-local-ci|frontend-local-ci)$'; then
        stale=true
    fi
    if docker compose -p rag_local_ci -f docker-compose.ci.yml ps -q 2>/dev/null | head -1 | grep -q .; then
        stale=true
    fi
    if [[ "$stale" == "true" ]]; then
        echo -e "${YELLOW}⚠ Found stale containers from a previous run — cleaning up${RESET}"
        cleanup
    fi
}

# ─── Stage Runner ─────────────────────────────────────────────────────────────

run_stage() {
    local stage_name="$1"
    local stage_func="${STAGE_FUNCTIONS[$stage_name]}"
    local prereqs="${STAGE_PREREQS[$stage_name]}"

    STAGE_ORDER+=("$stage_name")

    # Check prerequisites
    if ! check_stage_prereqs "$prereqs"; then
        echo -e "${YELLOW}⚠ Skipping ${stage_name} — missing prerequisites (${prereqs})${RESET}"
        STAGE_RESULTS[$stage_name]=-1
        STAGE_DURATIONS[$stage_name]=0
        return
    fi

    print_stage_header "$stage_name"

    local start_time
    start_time=$(date +%s)

    # Run the stage function (capture exit code without errexit interference)
    $stage_func && local exit_code=0 || local exit_code=$?

    local end_time
    end_time=$(date +%s)
    local duration=$(( end_time - start_time ))

    STAGE_RESULTS[$stage_name]=$exit_code
    STAGE_DURATIONS[$stage_name]=$duration

    if [[ $exit_code -eq 0 ]]; then
        echo -e "${GREEN}✓ ${stage_name} passed${RESET} ($(format_duration $duration))"
    else
        echo -e "${RED}✗ ${stage_name} failed${RESET} (exit code $exit_code, $(format_duration $duration))"
    fi
}

# ─── Summary ──────────────────────────────────────────────────────────────────

print_summary() {
    local total_start="$1"
    local total_end
    total_end=$(date +%s)
    local total_duration=$(( total_end - total_start ))

    local passed=0
    local failed=0
    local skipped=0

    print_header "Local CI Pipeline Results"

    for stage_name in "${STAGE_ORDER[@]}"; do
        local result=${STAGE_RESULTS[$stage_name]}
        local duration=${STAGE_DURATIONS[$stage_name]}
        local formatted_duration
        formatted_duration=$(format_duration "$duration")

        if [[ $result -eq 0 ]]; then
            echo -e "  ${GREEN}✓${RESET} $(printf '%-22s' "$stage_name") [$(printf '%6s' "$formatted_duration")]"
            passed=$(( passed + 1 ))
        elif [[ $result -eq -1 ]]; then
            echo -e "  ${YELLOW}-${RESET} $(printf '%-22s' "$stage_name") [${YELLOW}SKIPPED${RESET}]"
            skipped=$(( skipped + 1 ))
        else
            echo -e "  ${RED}✗${RESET} $(printf '%-22s' "$stage_name") [$(printf '%6s' "$formatted_duration")]"
            failed=$(( failed + 1 ))
        fi
    done

    print_separator

    local total_ran=$(( passed + failed ))
    local total_formatted
    total_formatted=$(format_duration "$total_duration")

    if [[ $failed -gt 0 ]]; then
        echo -e "  ${RED}${BOLD}FAILED${RESET} (${failed} of ${total_ran} stages failed)"
    else
        echo -e "  ${GREEN}${BOLD}PASSED${RESET} (${passed} stages passed)"
    fi

    if [[ $skipped -gt 0 ]]; then
        echo -e "  ${YELLOW}${skipped} stage(s) skipped${RESET}"
    fi

    echo -e "  Total time: ${BOLD}${total_formatted}${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"
    echo ""

    # Return non-zero if any stage failed
    [[ $failed -eq 0 ]]
}

# ─── Help ─────────────────────────────────────────────────────────────────────

show_help() {
    cat <<'HELP'
Usage: ./run-ci.sh [OPTIONS] [STAGE...]

Local CI Pipeline Runner — mirrors the GitHub Actions test pipeline locally.

OPTIONS:
  --help       Show this help text
  --quick      Run fast checks only (lint-backend, lint-frontend)
  --backend    Run backend stages (lint-backend, unit-tests, security-scan, resilience-tests)
  --frontend   Run frontend stages (lint-frontend, frontend-tests)
  --e2e        Run E2E tests (Docker full stack build + smoke tests)
  --auto       Auto-detect changed files and run relevant stages

AVAILABLE STAGES:
HELP

    for stage in "${ALL_STAGES[@]}"; do
        printf "  %-22s %s\n" "$stage" "${STAGE_DESCRIPTIONS[$stage]}"
    done

    cat <<'HELP'

EXIT CODES:
  0    All executed stages passed
  1    One or more stages failed
  2    Invalid arguments or usage error

ENVIRONMENT VARIABLES:
  NO_COLOR   Disable colorized output when set
  CI         Disable colorized output when set (CI compatibility)

EXAMPLES:
  ./run-ci.sh                          # Run all stages
  ./run-ci.sh --quick                  # Fast pre-push check (~2 min)
  ./run-ci.sh --backend                # Backend stages only
  ./run-ci.sh --frontend               # Frontend stages only
  ./run-ci.sh lint-backend unit-tests  # Run specific stages
  ./run-ci.sh --e2e                    # E2E smoke tests (Docker)
  ./run-ci.sh --auto                   # Auto-detect changes
HELP
    exit 0
}

# ─── Argument Parsing ─────────────────────────────────────────────────────────

is_valid_stage() {
    local name="$1"
    for stage in "${ALL_STAGES[@]}"; do
        [[ "$stage" == "$name" ]] && return 0
    done
    return 1
}

# Reorder selected stages to match canonical ALL_STAGES order
reorder_stages() {
    local -n selected=$1
    local ordered=()
    for stage in "${ALL_STAGES[@]}"; do
        for sel in "${selected[@]}"; do
            if [[ "$stage" == "$sel" ]]; then
                ordered+=("$stage")
                break
            fi
        done
    done
    selected=("${ordered[@]}")
}

parse_args() {
    SELECTED_STAGES=()
    local mode=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help
                ;;
            --quick)
                if [[ -n "$mode" ]]; then
                    echo "ERROR: Cannot combine --quick with --${mode}"
                    exit 2
                fi
                mode="quick"
                SELECTED_STAGES=(lint-backend lint-frontend)
                shift
                ;;
            --backend)
                if [[ -n "$mode" ]]; then
                    echo "ERROR: Cannot combine --backend with --${mode}"
                    exit 2
                fi
                mode="backend"
                SELECTED_STAGES=(lint-backend unit-tests security-scan resilience-tests)
                shift
                ;;
            --frontend)
                if [[ -n "$mode" ]]; then
                    echo "ERROR: Cannot combine --frontend with --${mode}"
                    exit 2
                fi
                mode="frontend"
                SELECTED_STAGES=(lint-frontend frontend-tests)
                shift
                ;;
            --e2e)
                if [[ -n "$mode" ]]; then
                    echo "ERROR: Cannot combine --e2e with --${mode}"
                    exit 2
                fi
                mode="e2e"
                SELECTED_STAGES=(e2e-tests)
                shift
                ;;
            --auto)
                if [[ -n "$mode" ]]; then
                    echo "ERROR: Cannot combine --auto with --${mode}"
                    exit 2
                fi
                if [[ "$HAS_GIT" != "true" ]]; then
                    echo "ERROR: --auto requires git"
                    exit 2
                fi
                mode="auto"
                shift
                ;;
            --*)
                echo "ERROR: Unknown option '$1'"
                echo "Run ./run-ci.sh --help for usage"
                exit 2
                ;;
            *)
                # Positional argument — stage name
                if [[ -n "$mode" && "$mode" != "stages" ]]; then
                    echo "ERROR: Cannot combine stage names with --${mode}"
                    exit 2
                fi
                if ! is_valid_stage "$1"; then
                    echo "ERROR: Unknown stage '$1'"
                    echo ""
                    echo "Available stages:"
                    for stage in "${ALL_STAGES[@]}"; do
                        echo "  $stage"
                    done
                    exit 2
                fi
                mode="stages"
                SELECTED_STAGES+=("$1")
                shift
                ;;
        esac
    done

    # Handle --auto mode (needs prereqs checked first)
    if [[ "$mode" == "auto" ]]; then
        echo -e "${BOLD}Detecting changes...${RESET}"
        local detected
        detected=$(detect_changed_stages)
        # Last line is the result
        local result
        result=$(echo "$detected" | tail -1)
        # Everything before is info messages — print them
        echo "$detected" | head -n -1

        if [[ "$result" == "ALL" ]]; then
            SELECTED_STAGES=("${ALL_STAGES[@]}")
        else
            IFS=' ' read -ra SELECTED_STAGES <<< "$result"
        fi
        echo ""
    fi

    # Default: run all stages
    if [[ ${#SELECTED_STAGES[@]} -eq 0 ]]; then
        SELECTED_STAGES=("${ALL_STAGES[@]}")
    fi

    # Reorder to canonical order
    if [[ "$mode" == "stages" ]]; then
        reorder_stages SELECTED_STAGES
    fi
}

# ─── Main ─────────────────────────────────────────────────────────────────────

main() {
    # Handle --help before anything else
    for arg in "$@"; do
        if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
            source scripts/ci/utils.sh 2>/dev/null || true
            show_help
        fi
    done

    local total_start
    total_start=$(date +%s)

    print_header "Local CI Pipeline"

    check_prereqs
    parse_args "$@"

    # Clean up stale containers from previous runs
    cleanup_stale

    echo -e "${BOLD}Running ${#SELECTED_STAGES[@]} stage(s):${RESET} ${SELECTED_STAGES[*]}"
    echo ""

    # Run selected stages sequentially (continue-all on failure)
    for stage_name in "${SELECTED_STAGES[@]}"; do
        run_stage "$stage_name"
    done

    # Print summary and exit with appropriate code
    print_summary "$total_start"
}

main "$@"
