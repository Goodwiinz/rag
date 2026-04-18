#!/bin/bash

# Test runner script for T3 Analytics Services

set -e

echo "🧪 Running T3 Analytics Services Test Suite"
echo "=========================================="

# Check if we're in the backend directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    exit 1
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "📦 Installing pytest and test dependencies..."
    pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
fi

# Create test directory if it doesn't exist
mkdir -p src/tests/{unit,integration,fixtures,reports}

echo "✅ Test environment ready"
echo ""

# Run unit tests
echo "🔬 Running Unit Tests..."
echo "========================"
PYTHONPATH=/app pytest src/tests/unit/ -v \
    --cov=src/services \
    --cov-report=term-missing \
    --cov-report=html:src/tests/reports/unit_coverage \
    --html=src/tests/reports/unit_report.html \
    --self-contained-html \
    -m "not integration" || echo "⚠️  Some unit tests failed"

echo ""

# Run integration tests
echo "🔗 Running Integration Tests..."
echo "=============================="
PYTHONPATH=/app pytest src/tests/integration/ -v \
    --cov=src/api \
    --cov-report=term-missing \
    --cov-report=html:src/tests/reports/integration_coverage \
    --html=src/tests/reports/integration_report.html \
    --self-contained-html \
    -m "integration" || echo "⚠️  Some integration tests failed"

echo ""

# Run all tests with coverage
echo "📊 Running Full Test Suite with Coverage..."
echo "========================================="
PYTHONPATH=/app pytest src/tests/ -v \
    --cov=src/services \
    --cov=src/api \
    --cov-report=term-missing \
    --cov-report=html:src/tests/reports/total_coverage \
    --html=src/tests/reports/total_report.html \
    --self-contained-html \
    --junit-xml=src/tests/reports/junit.xml \
    --durations=10 || echo "⚠️  Some tests failed"

echo ""

# Generate test summary
echo "📋 Test Summary"
echo "==============="
echo "Test reports generated in: src/tests/reports/"
echo "- Coverage report: src/tests/reports/total_coverage/index.html"
echo "- Test report: src/tests/reports/total_report.html"
echo "- JUnit XML: src/tests/reports/junit.xml"

# Check coverage threshold
COVERAGE_FILE="src/tests/reports/total_coverage/index.html"
if [ -f "$COVERAGE_FILE" ]; then
    # Extract coverage percentage from HTML report
    COVERAGE=$(grep -o '([0-9]\+%)' "$COVERAGE_FILE" | head -1 | sed 's/[()]//g')
    echo "📈 Total Coverage: $COVERAGE"

    if [ "${COVERAGE%?}" -ge "80" ]; then
        echo "✅ Coverage target (80%) met!"
    else
        echo "⚠️  Coverage below target (80%)"
    fi
fi

echo ""
echo "🎉 Test suite completed!"
echo "========================"

# Show any failed tests
echo "💡 To run specific test files:"
echo "   pytest src/tests/unit/test_quality_metrics_service.py"
echo ""
echo "💡 To run tests with specific markers:"
echo "   pytest -m unit"
echo "   pytest -m integration"
echo "   pytest -m 'not slow'"
echo ""
echo "💡 To run tests with verbose output:"
echo "   pytest -v -s src/tests/unit/test_*.py"