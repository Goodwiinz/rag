#!/bin/bash

# Monitoring System Test Runner
# Comprehensive test execution script for all monitoring system tests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Logging function
log() {
    echo -e "${BLUE}[$TIMESTAMP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$TIMESTAMP] ✓ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$TIMESTAMP] ⚠ $1${NC}"
}

log_error() {
    echo -e "${RED}[$TIMESTAMP] ✗ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    log_error "Please run this script from the root directory of the RAG system"
    exit 1
fi

# Configuration
RUN_BACKEND=${RUN_BACKEND:-true}
RUN_FRONTEND=${RUN_FRONTEND:-true}
RUN_E2E=${RUN_E2E:-true}
RUN_PERFORMANCE=${RUN_PERFORMANCE:-false}
RUN_ACCESSIBILITY=${RUN_ACCESSIBILITY:-true}
GENERATE_REPORTS=${GENERATE_REPORTS:-true}
PARALLEL_BACKEND=${PARALLEL_BACKEND:-true}
PARALLEL_FRONTEND=${PARALLEL_FRONTEND:-false}

# Results directory
RESULTS_DIR="test-results/monitoring-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

log "🚀 Starting Monitoring System Test Suite"
log "Results will be saved to: $RESULTS_DIR"

# Cleanup function
cleanup() {
    log "🧹 Cleaning up test environment..."

    # Stop test services
    if [ -f "docker-compose.test.yml" ]; then
        docker-compose -f docker-compose.test.yml down -v
    fi

    # Clean up temporary files
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
}

# Set up cleanup on exit
trap cleanup EXIT

# Function to check if a service is healthy
wait_for_service() {
    local service_name=$1
    local health_check_url=$2
    local max_attempts=${3:-30}
    local attempt=1

    log "Waiting for $service_name to be healthy..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$health_check_url" > /dev/null 2>&1; then
            log_success "$service_name is healthy"
            return 0
        fi

        log_warning "$service_name not ready (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    log_error "$service_name failed to become healthy"
    return 1
}

# Function to run backend tests
run_backend_tests() {
    if [ "$RUN_BACKEND" = false ]; then
        log "⏭️  Skipping backend tests"
        return 0
    fi

    log "📊 Running Backend Tests"

    cd backend

    # Create test environment file
    cat > .env.test << EOF
ENVIRONMENT=test
DEBUG=true
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///:memory:
REDIS_URL=redis://localhost:6379/1
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=testpassword
QDRANT_URL=http://localhost:6333
MONITORING_METRICS__CUSTOM_METRICS_ENABLED=true
MONITORING_TRACING__ENABLED=true
MONITORING_LOGGING__STRUCTURED_LOGGING=true
MONITORING_ALERTING__ENABLED=true
MONITORING_HEALTH_CHECK__ENABLED=true
EOF

    # Install dependencies if needed
    if [ ! -d "venv" ]; then
        log "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate
    pip install -q -r requirements.txt
    pip install -q -r requirements-dev.txt

    # Start test services
    log "🐳 Starting test services..."
    cd ..
    docker-compose -f docker-compose.test.yml up -d

    # Wait for services
    wait_for_service "PostgreSQL" "http://localhost:5432"
    wait_for_service "Redis" "http://localhost:6379"
    wait_for_service "Neo4j" "http://localhost:7474"
    wait_for_service "Qdrant" "http://localhost:6333"

    cd backend

    # Run database migrations
    log "🗄️ Running database migrations..."
    python -m alembic upgrade head || log_warning "Database migrations failed or not needed"

    # Test configuration
    PYTEST_ARGS="-v --tb=short --html=../$RESULTS_DIR/backend-report.html --self-contained-html"

    if [ "$PARALLEL_BACKEND" = true ]; then
        PYTEST_ARGS="$PYTEST_ARGS -n auto"
    fi

    # Run monitoring service integration tests
    log "🔧 Running Monitoring Service Integration Tests..."
    pytest tests/integration/test_monitoring_services_integration.py $PYTEST_ARGS \
        --junitxml=../$RESULTS_DIR/backend-service-integration.xml

    # Run WebSocket real-time tests
    log "🌐 Running WebSocket Real-time Tests..."
    pytest tests/integration/test_websocket_monitoring_realtime.py $PYTEST_ARGS \
        --junitxml=../$RESULTS_DIR/backend-websocket.xml

    # Run database integration tests
    log "🗄️ Running Database Integration Tests..."
    pytest tests/integration/test_database_monitoring_integration.py $PYTEST_ARGS \
        --junitxml=../$RESULTS_DIR/backend-database.xml

    # Run API integration tests
    log "🌍 Running API Integration Tests..."
    pytest tests/integration/test_monitoring_api_integration.py $PYTEST_ARGS \
        --junitxml=../$RESULTS_DIR/backend-api.xml

    # Run performance benchmarks
    if [ "$RUN_PERFORMANCE" = true ]; then
        log "⚡ Running Backend Performance Tests..."
        pytest tests/integration/test_monitoring_services_integration.py::TestMonitoringPerformanceBenchmarks \
            $PYTEST_ARGS --junitxml=../$RESULTS_DIR/backend-performance.xml
    fi

    # Generate coverage report
    log "📊 Generating Coverage Report..."
    pytest tests/integration/ --cov=src.monitoring --cov-report=html:../$RESULTS_DIR/backend-coverage \
        --cov-report=xml:../$RESULTS_DIR/backend-coverage.xml --cov-report=term-missing \
        --junitxml=../$RESULTS_DIR/backend-coverage.xml

    log_success "Backend tests completed"
    cd ..
}

# Function to run frontend tests
run_frontend_tests() {
    if [ "$RUN_FRONTEND" = false ]; then
        log "⏭️  Skipping frontend tests"
        return 0
    fi

    log "🎨 Running Frontend Tests"

    cd frontend

    # Install dependencies
    if [ ! -d "node_modules" ]; then
        log "Installing Node.js dependencies..."
        npm ci
    fi

    # Run component integration tests
    log "🧩 Running Component Integration Tests..."
    npm run test:integration 2>&1 | tee ../$RESULTS_DIR/frontend-component-tests.log

    # Check test results
    if [ $? -eq 0 ]; then
        log_success "Frontend component tests passed"
    else
        log_error "Frontend component tests failed"
    fi

    # Run accessibility tests
    if [ "$RUN_ACCESSIBILITY" = true ]; then
        log "♿ Running Accessibility Tests..."
        npm run test:accessibility 2>&1 | tee ../$RESULTS_DIR/frontend-accessibility-tests.log

        if [ $? -eq 0 ]; then
            log_success "Accessibility tests passed"
        else
            log_warning "Some accessibility tests failed"
        fi
    fi

    # Run Lighthouse CI tests
    if [ "$RUN_PERFORMANCE" = true ]; then
        log "🚀 Running Performance Tests..."
        npm run test:lighthouse 2>&1 | tee ../$RESULTS_DIR/frontend-lighthouse.log

        if [ $? -eq 0 ]; then
            log_success "Lighthouse tests passed"
        else
            log_warning "Some Lighthouse tests failed"
        fi
    fi

    log_success "Frontend tests completed"
    cd ..
}

# Function to run E2E tests
run_e2e_tests() {
    if [ "$RUN_E2E" = false ]; then
        log "⏭️  Skipping E2E tests"
        return 0
    fi

    log "🎭 Running E2E Tests"

    cd frontend

    # Install Playwright browsers
    if [ ! -d "$HOME/.cache/ms-playwright" ]; then
        log "Installing Playwright browsers..."
        npx playwright install --with-deps
    fi

    # Start the application
    log "🚀 Starting application for E2E tests..."
    npm run start &
    APP_PID=$!

    # Wait for application to be ready
    wait_for_service "Frontend App" "http://localhost:3000"

    # Run monitoring E2E tests
    log "🔍 Running Monitoring E2E Tests..."
    npx playwright test e2e/monitoring/ \
        --reporter=html,github \
        --output-dir=../$RESULTS_DIR/e2e-results \
        2>&1 | tee ../$RESULTS_DIR/e2e-tests.log

    # Check results
    if [ $? -eq 0 ]; then
        log_success "E2E tests passed"
    else
        log_error "E2E tests failed"
    fi

    # Stop the application
    kill $APP_PID 2>/dev/null || true
    cd ..
}

# Function to run load tests
run_load_tests() {
    if [ "$RUN_PERFORMANCE" = false ]; then
        log "⏭️  Skipping load tests"
        return 0
    fi

    log "⚡ Running Load Tests"

    # Check if k6 is installed
    if ! command -v k6 &> /dev/null; then
        log "Installing k6..."
        sudo gpg -k /usr/share/keyrings/k6-archive-keyring.gpg --dearmor
        sudo echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update
        sudo apt-get install k6
    fi

    # Ensure backend is running
    if ! pgrep -f "uvicorn.*main:app" > /dev/null; then
        log "Starting backend for load testing..."
        cd backend
        source venv/bin/activate
        uvicorn main:app --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!
        cd ..

        sleep 5
    fi

    # Run load tests
    cd tests/load

    log "📊 Running Load Test (100 concurrent users)..."
    k6 run k6-monitoring-load-test.js --out json=../$RESULTS_DIR/load-test-results.json

    log "⚡ Running Stress Test..."
    k6 run k6-monitoring-stress-test.js --out json=../$RESULTS_DIR/stress-test-results.json

    log "🚀 Running Spike Test..."
    k6 run k6-monitoring-spike-test.js --out json=../$RESULTS_DIR/spike-test-results.json

    # Generate performance report
    log "📊 Generating Performance Report..."
    python3 generate-load-test-report.py \
        --load-results ../$RESULTS_DIR/load-test-results.json \
        --stress-results ../$RESULTS_DIR/stress-test-results.json \
        --spike-results ../$RESULTS_DIR/spike-test-results.json \
        --output ../$RESULTS_DIR/performance-report.html

    cd ..

    # Stop backend if we started it
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi

    log_success "Load tests completed"
}

# Function to generate comprehensive report
generate_reports() {
    if [ "$GENERATE_REPORTS" = false ]; then
        return 0
    fi

    log "📊 Generating Comprehensive Test Report"

    # Create summary report
    cat > "$RESULTS_DIR/test-summary.md" << EOF
# Monitoring System Test Report

**Test Run Date:** $(date)
**Test Environment:** $ENVIRONMENT

## Test Results Summary

### Backend Tests
- Service Integration Tests: $(grep -c "passed" "$RESULTS_DIR/backend-service-integration.xml" 2>/dev/null || echo "0") passed
- WebSocket Tests: $(grep -c "passed" "$RESULTS_DIR/backend-websocket.xml" 2>/dev/null || echo "0") passed
- Database Tests: $(grep -c "passed" "$RESULTS_DIR/backend-database.xml" 2>/dev/null || echo "0") passed
- API Tests: $(grep -c "passed" "$RESULTS_DIR/backend-api.xml" 2>/dev/null || echo "0") passed

### Frontend Tests
- Component Tests: Check frontend-component-tests.log
- Accessibility Tests: Check frontend-accessibility-tests.log

### E2E Tests
- User Journey Tests: Check e2e-results/index.html

### Performance Tests
- Load Tests: Check load-test-results.json
- Stress Tests: Check stress-test-results.json
- Spike Tests: Check spike-test-results.json

## Coverage Reports
- Backend Coverage: [backend-coverage/index.html](backend-coverage/index.html)
- Frontend Coverage: Check coverage report in frontend

## Detailed Reports
- [Backend HTML Report]($RESULTS_DIR/backend-report.html)
- [E2E HTML Report]($RESULTS_DIR/e2e-results/index.html)
- [Performance Report]($RESULTS_DIR/performance-report.html)

## Files Generated
EOF

    # List all generated files
    ls -la "$RESULTS_DIR" >> "$RESULTS_DIR/test-summary.md"

    log_success "Comprehensive test report generated: $RESULTS_DIR/test-summary.md"
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-backend)
                RUN_BACKEND=false
                shift
                ;;
            --no-frontend)
                RUN_FRONTEND=false
                shift
                ;;
            --no-e2e)
                RUN_E2E=false
                shift
                ;;
            --no-performance)
                RUN_PERFORMANCE=false
                shift
                ;;
            --no-accessibility)
                RUN_ACCESSIBILITY=false
                shift
                ;;
            --no-reports)
                GENERATE_REPORTS=false
                shift
                ;;
            --parallel-backend)
                PARALLEL_BACKEND=true
                shift
                ;;
            --parallel-frontend)
                PARALLEL_FRONTEND=true
                shift
                ;;
            --performance)
                RUN_PERFORMANCE=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --no-backend       Skip backend tests"
                echo "  --no-frontend      Skip frontend tests"
                echo "  --no-e2e           Skip E2E tests"
                echo "  --no-performance   Skip performance tests"
                echo "  --no-accessibility Skip accessibility tests"
                echo "  --no-reports       Skip report generation"
                echo "  --parallel-backend Run backend tests in parallel"
                echo "  --parallel-frontend Run frontend tests in parallel"
                echo "  --performance      Enable performance tests"
                echo "  --help            Show this help message"
                exit 0
                ;;
            *)
                log_warning "Unknown option: $1"
                shift
                ;;
        esac
    done

    # Execute test suites
    local start_time=$(date +%s)

    run_backend_tests
    run_frontend_tests
    run_e2e_tests
    run_load_tests
    generate_reports

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_success "🎉 All tests completed in ${duration} seconds!"
    log "📁 Results available in: $RESULTS_DIR"

    # Show summary
    echo
    echo "=== Test Summary ==="
    echo "Results Directory: $RESULTS_DIR"
    echo "Duration: ${duration} seconds"
    echo ""
    echo "Generated Reports:"
    echo "- Backend HTML: $RESULTS_DIR/backend-report.html"
    echo "- Backend Coverage: $RESULTS_DIR/backend-coverage/index.html"
    echo "- E2E Report: $RESULTS_DIR/e2e-results/index.html"
    echo "- Summary: $RESULTS_DIR/test-summary.md"

    if [ "$RUN_PERFORMANCE" = true ]; then
        echo "- Performance Report: $RESULTS_DIR/performance-report.html"
    fi
}

# Check dependencies
check_dependencies() {
    log "🔍 Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required"
        exit 1
    fi

    # Check Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is required"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is required"
        exit 1
    fi

    log_success "All dependencies are available"
}

# Run dependency check
check_dependencies

# Execute main function
main "$@"