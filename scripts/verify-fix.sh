#!/bin/bash
# verify-fix.sh - Automated verification script for code fixes
#
# Usage: ./scripts/verify-fix.sh --file <file_path> [--issue <issue-id>] [--rollback]
#
# This script runs comprehensive verification after applying a code fix:
# 1. Detects file type (Python/TypeScript/etc.)
# 2. Runs type checks
# 3. Runs linting
# 4. Runs relevant tests
# 5. Reports results
# 6. Optionally rolls back on failure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
FILE_PATH=""
ISSUE_ID=""
ROLLBACK_ON_FAIL=false
VERBOSE=false
RESULTS_FILE="/tmp/verify-fix-results.json"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --file|-f)
            FILE_PATH="$2"
            shift 2
            ;;
        --issue|-i)
            ISSUE_ID="$2"
            shift 2
            ;;
        --rollback|-r)
            ROLLBACK_ON_FAIL=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 --file <file_path> [--issue <issue-id>] [--rollback] [--verbose]"
            echo ""
            echo "Options:"
            echo "  --file, -f      Path to the modified file (required)"
            echo "  --issue, -i     Linear issue ID (e.g., GOO-31)"
            echo "  --rollback, -r  Rollback changes on verification failure"
            echo "  --verbose, -v   Show detailed output"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$FILE_PATH" ]]; then
    echo -e "${RED}Error: --file is required${NC}"
    exit 1
fi

# Initialize results
init_results() {
    # Use environment variables to avoid shell injection in JSON generation
    INIT_FILE_PATH="$FILE_PATH" \
    INIT_ISSUE_ID="$ISSUE_ID" \
    INIT_RESULTS_FILE="$RESULTS_FILE" \
    python3 << 'EOF'
import json
import os
from datetime import datetime, timezone

data = {
    "file": os.environ.get("INIT_FILE_PATH", ""),
    "issue": os.environ.get("INIT_ISSUE_ID", ""),
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "checks": {},
    "overall": "pending"
}
with open(os.environ["INIT_RESULTS_FILE"], "w") as f:
    json.dump(data, f, indent=2)
EOF
}

# Update results
update_result() {
    local check_name="$1"
    local status="$2"
    local message="$3"

    # Use environment variables to avoid shell injection in JSON manipulation
    UPDATE_RESULTS_FILE="$RESULTS_FILE" \
    UPDATE_CHECK_NAME="$check_name" \
    UPDATE_STATUS="$status" \
    UPDATE_MESSAGE="$message" \
    python3 << 'EOF'
import json
import os

results_file = os.environ["UPDATE_RESULTS_FILE"]
check_name = os.environ["UPDATE_CHECK_NAME"]
status = os.environ["UPDATE_STATUS"]
message = os.environ["UPDATE_MESSAGE"]

with open(results_file, "r") as f:
    data = json.load(f)
data["checks"][check_name] = {"status": status, "message": message}
with open(results_file, "w") as f:
    json.dump(data, f, indent=2)
EOF
}

# Finalize results
finalize_results() {
    local overall="$1"

    # Use environment variables to avoid shell injection in JSON manipulation
    FINALIZE_RESULTS_FILE="$RESULTS_FILE" \
    FINALIZE_OVERALL="$overall" \
    python3 << 'EOF'
import json
import os

results_file = os.environ["FINALIZE_RESULTS_FILE"]
overall = os.environ["FINALIZE_OVERALL"]

with open(results_file, "r") as f:
    data = json.load(f)
data["overall"] = overall
with open(results_file, "w") as f:
    json.dump(data, f, indent=2)
EOF
}

# Print section header
print_header() {
    echo ""
    echo -e "${CYAN}=== $1 ===${NC}"
}

# Print result
print_result() {
    local status="$1"
    local message="$2"
    if [[ "$status" == "pass" ]]; then
        echo -e "${GREEN}✓ $message${NC}"
    elif [[ "$status" == "fail" ]]; then
        echo -e "${RED}✗ $message${NC}"
    elif [[ "$status" == "skip" ]]; then
        echo -e "${YELLOW}○ $message${NC}"
    else
        echo -e "  $message"
    fi
}

# Detect file type
detect_file_type() {
    local file="$1"
    local ext="${file##*.}"

    case "$ext" in
        py)
            echo "python"
            ;;
        ts|tsx)
            echo "typescript"
            ;;
        js|jsx)
            echo "javascript"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Check Python file
check_python() {
    local file="$1"
    local all_passed=true

    print_header "Python Verification"

    # Syntax check
    if python3 -m py_compile "$file" 2>/dev/null; then
        print_result "pass" "Syntax check"
        update_result "syntax" "pass" "No syntax errors"
    else
        print_result "fail" "Syntax check"
        update_result "syntax" "fail" "Syntax errors found"
        all_passed=false
    fi

    # Type check with mypy (if available)
    if command -v mypy &> /dev/null; then
        if mypy "$file" --ignore-missing-imports --no-error-summary 2>/dev/null; then
            print_result "pass" "Type check (mypy)"
            update_result "type_check" "pass" "No type errors"
        else
            print_result "fail" "Type check (mypy)"
            update_result "type_check" "fail" "Type errors found"
            all_passed=false
        fi
    else
        print_result "skip" "Type check (mypy not installed)"
        update_result "type_check" "skip" "mypy not installed"
    fi

    # Lint with ruff (if available)
    if command -v ruff &> /dev/null; then
        if ruff check "$file" --quiet 2>/dev/null; then
            print_result "pass" "Lint check (ruff)"
            update_result "lint" "pass" "No lint errors"
        else
            print_result "fail" "Lint check (ruff)"
            update_result "lint" "fail" "Lint errors found"
            all_passed=false
        fi
    else
        print_result "skip" "Lint check (ruff not installed)"
        update_result "lint" "skip" "ruff not installed"
    fi

    # Run related tests
    local test_dir="$PROJECT_ROOT/tests"
    local module_name
    module_name=$(basename "$file" .py)

    if [[ -d "$test_dir" ]]; then
        if pytest "$test_dir" -x --tb=short -q -k "$module_name" 2>/dev/null; then
            print_result "pass" "Tests (pytest)"
            update_result "tests" "pass" "Tests passed"
        else
            # Check if no tests matched (which is OK)
            if pytest "$test_dir" --collect-only -q -k "$module_name" 2>/dev/null | grep -q "no tests ran"; then
                print_result "skip" "Tests (no matching tests found)"
                update_result "tests" "skip" "No matching tests"
            else
                print_result "fail" "Tests (pytest)"
                update_result "tests" "fail" "Tests failed"
                all_passed=false
            fi
        fi
    else
        print_result "skip" "Tests (test directory not found)"
        update_result "tests" "skip" "Test directory not found"
    fi

    if $all_passed; then
        return 0
    else
        return 1
    fi
}

# Check TypeScript/JavaScript file
check_typescript() {
    local file="$1"
    local all_passed=true
    local frontend_dir="$PROJECT_ROOT/frontend"

    print_header "TypeScript/JavaScript Verification"

    # Check if frontend directory exists
    if [[ ! -d "$frontend_dir" ]]; then
        print_result "skip" "Frontend directory not found"
        update_result "frontend_check" "skip" "Frontend directory not found"
        return 0
    fi

    cd "$frontend_dir"

    # Type check
    if npm run type-check 2>/dev/null; then
        print_result "pass" "Type check (tsc)"
        update_result "type_check" "pass" "No type errors"
    else
        print_result "fail" "Type check (tsc)"
        update_result "type_check" "fail" "Type errors found"
        all_passed=false
    fi

    # Lint check
    if npm run lint -- --quiet 2>/dev/null; then
        print_result "pass" "Lint check (eslint)"
        update_result "lint" "pass" "No lint errors"
    else
        print_result "fail" "Lint check (eslint)"
        update_result "lint" "fail" "Lint errors found"
        all_passed=false
    fi

    cd "$PROJECT_ROOT"

    if $all_passed; then
        return 0
    else
        return 1
    fi
}

# Rollback changes
rollback() {
    local file="$1"
    print_header "Rolling Back Changes"

    if git checkout -- "$file" 2>/dev/null; then
        print_result "pass" "Rolled back: $file"
        return 0
    else
        print_result "fail" "Failed to rollback: $file"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Code Fix Verification Script         ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "File: ${YELLOW}$FILE_PATH${NC}"
    [[ -n "$ISSUE_ID" ]] && echo -e "Issue: ${YELLOW}$ISSUE_ID${NC}"

    # Initialize results
    init_results

    # Check if file exists
    if [[ ! -f "$FILE_PATH" ]]; then
        echo -e "${RED}Error: File not found: $FILE_PATH${NC}"
        finalize_results "error"
        exit 1
    fi

    # Detect file type and run appropriate checks
    local file_type
    file_type=$(detect_file_type "$FILE_PATH")
    local verification_passed=true

    case "$file_type" in
        python)
            if ! check_python "$FILE_PATH"; then
                verification_passed=false
            fi
            ;;
        typescript|javascript)
            if ! check_typescript "$FILE_PATH"; then
                verification_passed=false
            fi
            ;;
        *)
            print_header "Unknown File Type"
            print_result "skip" "No verification available for .$file_type files"
            update_result "unknown" "skip" "No verification for this file type"
            ;;
    esac

    # Summary
    print_header "Summary"

    if $verification_passed; then
        echo -e "${GREEN}All verification checks passed!${NC}"
        finalize_results "pass"

        # Show results file location
        echo ""
        echo -e "Results saved to: ${CYAN}$RESULTS_FILE${NC}"
        exit 0
    else
        echo -e "${RED}Some verification checks failed.${NC}"
        finalize_results "fail"

        if $ROLLBACK_ON_FAIL; then
            rollback "$FILE_PATH"
        else
            echo ""
            echo -e "${YELLOW}Tip: Use --rollback to automatically revert on failure${NC}"
        fi

        # Show results file location
        echo ""
        echo -e "Results saved to: ${CYAN}$RESULTS_FILE${NC}"
        exit 1
    fi
}

# Run main
main
