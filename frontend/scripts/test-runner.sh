#!/bin/bash

# Test Runner Script for Multimodal Enterprise RAG Frontend
# This script runs comprehensive tests and generates coverage reports

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to run tests with timeout
run_test_with_timeout() {
    local test_command="$1"
    local timeout_duration="${2:-300}"
    local test_name="${3:-test}"

    print_status "Running $test_name..."

    if command_exists gtimeout; then
        gtimeout "$timeout_duration" bash -c "$test_command" || {
            print_error "$test_name timed out after ${timeout_duration}s"
            return 1
        }
    else
        timeout "$timeout_duration" bash -c "$test_command" || {
            print_error "$test_name timed out after ${timeout_duration}s"
            return 1
        }
    fi

    return 0
}

# Function to check test dependencies
check_dependencies() {
    print_status "Checking test dependencies..."

    local missing_deps=()

    # Check for Node.js
    if ! command_exists node; then
        missing_deps+=("Node.js")
    fi

    # Check for npm/yarn
    if ! command_exists npm && ! command_exists yarn; then
        missing_deps+=("npm or yarn")
    fi

    # Check for required test dependencies
    local test_deps=("jest" "typescript" "@testing-library/react" "@testing-library/jest-dom")
    for dep in "${test_deps[@]}"; do
        if ! npm list "$dep" --depth=0 --prefix &>/dev/null && ! yarn list "$dep" --depth=0 --silent &>/dev/null; then
            missing_deps+=("$dep")
        fi
    done

    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        print_status "Please install missing dependencies with:"
        print_status "  npm install ${missing_deps[*]}"
        print_status "or"
        print_status "  yarn add ${missing_deps[*]}"
        return 1
    fi

    print_success "All dependencies are installed"
}

# Function to clean up test artifacts
cleanup_test_artifacts() {
    print_status "Cleaning up test artifacts..."

    # Remove coverage directory
    if [ -d "coverage" ]; then
        rm -rf coverage
        print_status "Removed coverage directory"
    fi

    # Remove Jest cache
    if [ -d "node_modules/.cache" ]; then
        rm -rf node_modules/.cache
        print_status "Cleared Jest cache"
    fi

    # Remove test temporary files
    find . -name "*.log" -type f -delete 2>/dev/null || true
    find . -name ".jest-test-results.json" -type f -delete 2>/dev/null || true

    print_success "Test artifacts cleaned up"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing dependencies..."

    # Use npm if available, otherwise yarn
    if command_exists npm; then
        npm ci
    elif command_exists yarn; then
        yarn install --frozen-lockfile
    else
        print_error "Neither npm nor yarn found. Please install Node.js and npm/yarn."
        return 1
    fi

    print_success "Dependencies installed"
}

# Function to run linting
run_linting() {
    print_status "Running linting..."

    if npm run lint --silent 2>/dev/null; then
        print_success "Linting passed"
    else
        print_error "Linting failed. Please fix linting errors before proceeding."
        return 1
    fi
}

# Function to run type checking
run_type_check() {
    print_status "Running TypeScript type checking..."

    if npm run type-check 2>/dev/null; then
        print_success "Type checking passed"
    else
        print_error "Type checking failed. Please fix type errors before proceeding."
        return 1
    fi
}

# Function to run unit tests
run_unit_tests() {
    print_status "Running unit tests..."

    if run_test_with_timeout "npm run test:unit" 120 "Unit Tests"; then
        print_success "Unit tests passed"
    else
        print_error "Unit tests failed"
        return 1
    fi
}

# Function to run component tests
run_component_tests() {
    print_status "Running component tests..."

    if run_test_with_timeout "npm run test:component" 120 "Component Tests"; then
        print_success "Component tests passed"
    else
        print_error "Component tests failed"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    print_status "Running integration tests..."

    if run_test_with_timeout "npm run test:integration" 180 "Integration Tests"; then
        print_success "Integration tests passed"
    else
        print_error "Integration tests failed"
        return 1
    fi
}

# Function to run service tests
run_service_tests() {
    print_status "Running service tests..."

    if run_test_with_timeout "npm run test:services" 120 "Service Tests"; then
        print_success "Service tests passed"
    else
        print_error "Service tests failed"
        return 1
    fi
}

# Function to run utility tests
run_utility_tests() {
    print_status "Running utility tests..."

    if run_test_with_timeout "npm run test:utils" 60 "Utility Tests"; then
        print_success "Utility tests passed"
    else
        print_error "Utility tests failed"
        return 1
    fi
}

# Function to run all tests
run_all_tests() {
    print_status "Running all tests..."

    if run_test_with_timeout "npm run test:all" 300 "All Tests"; then
        print_success "All tests passed"
    else
        print_error "Some tests failed"
        return 1
    fi
}

# Function to run tests with coverage
run_coverage_tests() {
    print_status "Running tests with coverage analysis..."

    cleanup_test_artifacts

    if run_test_with_timeout "npm run test:coverage" 300 "Coverage Tests"; then
        print_success "Coverage tests completed"

        # Display coverage summary
        if [ -f "coverage/coverage-summary.json" ]; then
            print_status "Coverage Summary:"
            node -e "
                const summary = require('./coverage/coverage-summary.json');
                console.log('Lines:', summary.total.lines.pct + '%');
                console.log('Functions:', summary.total.functions.pct + '%');
                console.log('Branches:', summary.total.branches.pct + '%');
                console.log('Statements:', summary.total.statements.pct + '%');
            " coverage/coverage-summary.json

            # Check if coverage meets thresholds
            lines=$(node -p "console.log(JSON.parse(require('./coverage/coverage-summary.json').total.lines.pct)" coverage/coverage-summary.json)
            functions=$(node -p "console.log(JSON.parse(require('./coverage/coverage-summary.json').total.functions.pct)" coverage/coverage-summary.json)
            branches=$(node -p "console.log(JSON.parse(require('./coverage/coverage-summary.json').total.branches.pct)" coverage/coverage-summary.json)
            statements=$(node -p "console.log(JSON.parse(require('./coverage/coverage-summary.json').total.statements.pct)" coverage/coverage-summary.json)

            lines_num=${lines%.*}
            if [ "$lines_num" -lt 70 ]; then
                print_warning "Line coverage (${lines}%) is below the 70% threshold"
            else
                print_success "Line coverage (${lines}%) meets the 70% threshold"
            fi

            functions_num=${functions%.*}
            if [ "$functions_num" -lt 70 ]; then
                print_warning "Function coverage (${functions}%) is below the 70% threshold"
            else
                print_success "Function coverage (${functions}%) meets the 70% threshold"
            fi

            branches_num=${branches%.*}
            if [ "$branches_num" -lt 70 ]; then
                print_warning "Branch coverage (${branches}%) is below the 70% threshold"
            else
                print_success "Branch coverage (${branches}%) meets the 70% threshold"
            fi

            statements_num=${statements%.*}
            if [ "$statements_num" -lt 70 ]; then
                print_warning "Statement coverage (${statements}%) is below the 70% threshold"
            else
                print_success "Statement coverage (${statements}%) meets the 70% threshold"
            fi
        fi

        # Open coverage report in browser if running interactively
        if [ -t 1 ]; then
            print_status "Coverage report generated. Opening in browser..."
            if command_exists open; then
                open coverage/lcov-report/index.html
            elif command_exists xdg-open; then
                    xdg-open coverage/lcov-report/index.html
                else
                    print_status "Coverage report available at: coverage/lcov-report/index.html"
                fi
        fi
    else
        print_error "Coverage tests failed"
        return 1
    fi
}

# Function to run tests in CI mode
run_ci_tests() {
    print_status "Running tests in CI mode..."

    # Set environment variables for CI
    export CI=true
    export NODE_ENV=test

    cleanup_test_artifacts

    # Run tests with coverage
    if npm run test:ci; then
        print_success "CI tests completed successfully"

        # Upload coverage if configured
        if [ -n "$CODECOV_TOKEN" ]; then
            print_status "Uploading coverage to Codecov..."
            bash <(curl -s https://codecov.io/bash) <<EOF
                -f coverage/lcov.info
                -B $BRANCH_NAME
                -C $COMMIT_SHA
                -n $BUILD_NUMBER
                -n $CIRCLE_BUILD_NUM
                -n $CI_BUILD_ID
            EOF

            print_success "Coverage uploaded to Codecov"
        fi
    else
        print_error "CI tests failed"
        return 1
    fi
}

# Function to generate test report
generate_test_report() {
    print_status "Generating test report..."

    local report_file="test-report-$(date +%Y-%m-%d-%H-%M-%S).json"

    # Create test report
    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "node_version": "$(node --version)",
  "npm_version": "$(npm --version)",
  "test_results": {
    "unit": "$(npm run test:unit --silent --json 2>/dev/null || echo '{}')",
    "component": "$(npm run test:component --silent --json 2>/dev/null || echo '{}')",
    "integration": "$(npm run test:integration --silent --json 2>/dev/null || echo '{}')",
    "services": "$(npm run test:services --silent --json 2>/dev/null || echo '{}')",
    "utils": "$(npm run test:utils --silent --json 2>/dev/null || echo '{}')"
  },
  "coverage": "$(npm run test:coverage --silent --json 2>/dev/null || echo '{}')"
}
EOF

    print_success "Test report generated: $report_file"
}

# Function to validate test configuration
validate_test_config() {
    print_status "Validating test configuration..."

    # Check Jest configuration
    if [ ! -f "jest.config.js" ]; then
        print_warning "Jest configuration file not found (jest.config.js)"
    else
        print_success "Jest configuration found"
    fi

    # Check test setup
    if [ ! -f "src/setupTests.ts" ]; then
        print_warning "Test setup file not found (src/setupTests.ts)"
    else
        print_success "Test setup file found"
    fi

    # Check test directories
    local test_dirs=(
        "src/components/__tests__"
        "src/utils/__tests__"
        "src/services/__tests__"
    )

    for dir in "${test_dirs[@]}"; do
        if [ -d "$dir" ]; then
            local test_count=$(find "$dir" -name "*.test.*" -o -name "*.spec.*" | wc -l)
            print_status "$dir: $test_count test files"
        else
            print_warning "Test directory not found: $dir"
        fi
    done
}

# Function to show help
show_help() {
    cat << EOF
Usage: $0 [OPTION]

Test Runner Script for Multimodal Enterprise RAG Frontend

OPTIONS:
  help, -h, --help        Show this help message
  check-deps             Check if test dependencies are installed
  install-deps          Install test dependencies
  clean                 Clean up test artifacts
  lint                  Run ESLint
  type-check             Run TypeScript type checking
  unit                  Run unit tests
  component              Run component tests
  integration           Run integration tests
  services              Run service tests
  utils                  Run utility tests
  all                    Run all tests
  coverage               Run tests with coverage
  ci                     Run tests in CI mode
  report                 Generate test report
  validate-config        Validate test configuration

EXAMPLES:
  $0                     Run all tests
  $0 unit                Run only unit tests
  $0 coverage             Run tests with coverage
  $0 ci                   Run tests in CI mode
  $0 clean                Clean up test artifacts
  $0 install-deps         Install test dependencies

ENVIRONMENT VARIABLES:
  CI                     Set to 'true' to run in CI mode
  NODE_ENV               Set to 'test' for testing
  CODECOV_TOKEN          Codecov token for coverage upload
  BRANCH_NAME            Git branch name for coverage
  COMMIT_SHA              Git commit SHA for coverage
  BUILD_NUMBER           Build number for coverage
  CIRCLE_BUILD_NUM        CircleCI build number
  CI_BUILD_ID             CI build ID

EOF
}

# Parse command line arguments
case "${1:-}" in
    help|--help|-h)
        show_help
        exit 0
        ;;
    check-deps)
        check_dependencies
        exit 0
        ;;
    install-deps)
        install_dependencies
        exit 0
        ;;
    clean)
        cleanup_test_artifacts
        exit 0
        ;;
    lint)
        run_linting
        exit 0
        ;;
    type-check)
        run_type_check
        exit 0
        ;;
    unit)
        run_unit_tests
        exit 0
        ;;
    component)
        run_component_tests
        exit 0
        ;;
    integration)
        run_integration_tests
        exit 0
        ;;
    services)
        run_service_tests
        exit 0
        ;;
    utils)
        run_utility_tests
        exit 0
        ;;
    all)
        run_all_tests
        exit 0
        ;;
    coverage)
        run_coverage_tests
        exit 0
        ;;
    ci)
        run_ci_tests
        exit 0
        ;;
    report)
        generate_test_report
        exit 0
        ;;
    validate-config)
        validate_test_config
        exit 0
        ;;
    "")
        # Default behavior: run all tests
        run_all_tests
        exit 0
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac