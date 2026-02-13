#!/usr/bin/env bash
# tests/ci/test_run_ci.sh — Smoke tests for run-ci.sh
# Validates CLI interface contract without running actual CI stages
set -uo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
cd "$PROJECT_ROOT" || exit 1

PASS=0
FAIL=0

assert_exit_code() {
    local description="$1"
    local expected="$2"
    local actual="$3"

    if [[ "$actual" -eq "$expected" ]]; then
        echo "  PASS: $description (exit $actual)"
        PASS=$(( PASS + 1 ))
    else
        echo "  FAIL: $description (expected exit $expected, got $actual)"
        FAIL=$(( FAIL + 1 ))
    fi
}

assert_output_contains() {
    local description="$1"
    local pattern="$2"
    local output="$3"

    if echo "$output" | grep -qE -- "$pattern"; then
        echo "  PASS: $description"
        PASS=$(( PASS + 1 ))
    else
        echo "  FAIL: $description (pattern '$pattern' not found)"
        FAIL=$(( FAIL + 1 ))
    fi
}

echo "=== run-ci.sh Smoke Tests ==="
echo ""

# ─── Test: --help exits 0 ─────────────────────────────────────────────────────
echo "Test: --help"
output=$(NO_COLOR=1 ./run-ci.sh --help 2>&1)
assert_exit_code "--help exits 0" 0 $?
assert_output_contains "--help shows usage line" "Usage:.*run-ci.sh" "$output"
assert_output_contains "--help shows stages" "lint-backend" "$output"
assert_output_contains "--help shows options" "--quick" "$output"

# ─── Test: -h exits 0 ─────────────────────────────────────────────────────────
echo ""
echo "Test: -h"
output=$(NO_COLOR=1 ./run-ci.sh -h 2>&1)
assert_exit_code "-h exits 0" 0 $?

# ─── Test: unknown stage exits 2 ──────────────────────────────────────────────
echo ""
echo "Test: unknown stage"
output=$(NO_COLOR=1 ./run-ci.sh nonexistent-stage 2>&1)
assert_exit_code "unknown stage exits 2" 2 $?
assert_output_contains "unknown stage shows error" "Unknown stage" "$output"

# ─── Test: unknown option exits 2 ─────────────────────────────────────────────
echo ""
echo "Test: unknown option"
output=$(NO_COLOR=1 ./run-ci.sh --bogus 2>&1)
assert_exit_code "unknown option exits 2" 2 $?
assert_output_contains "unknown option shows error" "Unknown option" "$output"

# ─── Test: conflicting flags exit 2 ───────────────────────────────────────────
echo ""
echo "Test: conflicting flags"
output=$(NO_COLOR=1 ./run-ci.sh --quick --backend 2>&1)
assert_exit_code "conflicting flags exit 2" 2 $?
assert_output_contains "conflicting flags show error" "Cannot combine" "$output"

# ─── Test: stage + flag conflict exits 2 ──────────────────────────────────────
echo ""
echo "Test: stage + flag conflict"
output=$(NO_COLOR=1 ./run-ci.sh --quick lint-backend 2>&1)
assert_exit_code "stage + flag conflict exits 2" 2 $?

# ─── Test: NO_COLOR disables ANSI codes ───────────────────────────────────────
echo ""
echo "Test: NO_COLOR"
output=$(NO_COLOR=1 ./run-ci.sh --help 2>&1)
if echo "$output" | grep -qP '\033\['; then
    echo "  FAIL: NO_COLOR still contains ANSI codes"
    FAIL=$(( FAIL + 1 ))
else
    echo "  PASS: NO_COLOR disables ANSI codes"
    PASS=$(( PASS + 1 ))
fi

# ─── Test: subdirectory invocation ────────────────────────────────────────────
echo ""
echo "Test: subdirectory invocation"
output=$(cd frontend && NO_COLOR=1 ../run-ci.sh --help 2>&1)
assert_exit_code "subdirectory invocation exits 0" 0 $?
assert_output_contains "subdirectory detects project root" "Detected project root|Usage:" "$output"

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "==========================="
echo "Results: $PASS passed, $FAIL failed"
echo "==========================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
