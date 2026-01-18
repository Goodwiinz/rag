# Makefile for RAG System Backend Testing
# Following Temporal Python Testing skill patterns for comprehensive test automation

.PHONY: test test-unit test-integration test-e2e test-chat test-search test-quick coverage lint format clean help

# Default target
help:
	@echo "RAG System Backend Test Commands"
	@echo "================================="
	@echo ""
	@echo "Test Execution:"
	@echo "  make test              - Run all tests with coverage"
	@echo "  make test-unit         - Run unit tests only (fast)"
	@echo "  make test-integration  - Run integration tests"
	@echo "  make test-e2e          - Run end-to-end tests"
	@echo "  make test-chat         - Run chat service tests"
	@echo "  make test-search       - Run search service tests"
	@echo "  make test-quick        - Run quick tests (skip slow)"
	@echo ""
	@echo "Coverage:"
	@echo "  make coverage          - Generate coverage report"
	@echo "  make coverage-html     - Open HTML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linters (ruff, mypy)"
	@echo "  make format            - Format code (ruff format)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Remove build artifacts"
	@echo ""

# =============================================================================
# Test Execution
# =============================================================================

# Run all tests with coverage
test:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html:coverage_html

# Run unit tests only (fast, no external dependencies)
test-unit:
	pytest tests/unit/ -v -m unit --cov=src --cov-report=term-missing

# Run integration tests
test-integration:
	pytest tests/integration/ -v -m integration

# Run end-to-end tests
test-e2e:
	pytest tests/e2e/ -v -m e2e

# Run chat service tests
test-chat:
	pytest tests/ -v -m chat --cov=src/services/chat_service.py --cov-report=term-missing

# Run search service tests
test-search:
	pytest tests/ -v -m search --cov=src/services/search_service.py --cov-report=term-missing

# Run quick tests (skip slow tests)
test-quick:
	pytest tests/ -v -m "not slow" --tb=short

# Run tests in parallel (requires pytest-xdist)
test-parallel:
	pytest tests/ -v -n auto --cov=src --cov-report=term-missing

# Run tests with verbose output
test-verbose:
	pytest tests/ -vvv --tb=long

# Run failed tests only
test-failed:
	pytest tests/ --lf -v

# Run last failed tests first
test-failed-first:
	pytest tests/ --ff -v

# =============================================================================
# Coverage
# =============================================================================

# Generate coverage report
coverage:
	pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:coverage_html --cov-report=xml:coverage.xml
	@echo ""
	@echo "HTML report generated at: coverage_html/index.html"
	@echo "XML report generated at: coverage.xml"

# Open HTML coverage report
coverage-html: coverage
	@if command -v open >/dev/null 2>&1; then \
		open coverage_html/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open coverage_html/index.html; \
	else \
		echo "Open coverage_html/index.html in your browser"; \
	fi

# Check coverage threshold (60% minimum)
coverage-check:
	pytest tests/ --cov=src --cov-fail-under=60

# =============================================================================
# Code Quality
# =============================================================================

# Run linters
lint:
	ruff check src tests
	mypy src --ignore-missing-imports

# Format code
format:
	ruff format src tests

# Check formatting without making changes
format-check:
	ruff format --check src tests

# Run all code quality checks
quality: lint format-check

# =============================================================================
# Development Helpers
# =============================================================================

# Install test dependencies
install-test-deps:
	pip install pytest pytest-asyncio pytest-cov pytest-xdist pytest-timeout ruff mypy

# Create test file from template
create-test:
	@read -p "Test file name (e.g., test_my_service): " name; \
	echo "Creating tests/unit/$$name.py"; \
	cp tests/templates/test_template.py tests/unit/$$name.py 2>/dev/null || \
	echo "# Test file for $$name" > tests/unit/$$name.py

# Watch for changes and run tests
watch:
	@echo "Watching for changes..."
	@which watchmedo >/dev/null 2>&1 || pip install watchdog
	watchmedo shell-command \
		--patterns="*.py" \
		--recursive \
		--command='make test-quick' \
		src tests

# =============================================================================
# Cleanup
# =============================================================================

# Clean build artifacts
clean:
	rm -rf coverage_html .coverage coverage.xml coverage.json
	rm -rf .pytest_cache __pycache__ .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage*" -delete 2>/dev/null || true

# Deep clean (including virtual environments)
clean-all: clean
	rm -rf venv .venv

# =============================================================================
# CI/CD Integration
# =============================================================================

# CI test run (suitable for GitHub Actions)
ci-test:
	pytest tests/ -v --tb=short --cov=src --cov-report=xml --cov-fail-under=60 --junitxml=test-results.xml

# Pre-commit checks
pre-commit: lint format-check test-quick
	@echo "All pre-commit checks passed!"
