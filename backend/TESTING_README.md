# Testing Environment Setup Guide

This guide covers the complete testing environment setup for the Multi-Agent Search System.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Test Structure](#test-structure)
5. [Running Tests](#running-tests)
6. [Test Categories](#test-categories)
7. [Mock Data and Fixtures](#mock-data-and-fixtures)
8. [Performance Testing](#performance-testing)
9. [Continuous Integration](#continuous-integration)
10. [Troubleshooting](#troubleshooting)

## Overview

The testing environment is designed to provide comprehensive coverage for the multi-agent search system, including:

- **Unit Tests**: Fast tests for individual components
- **Integration Tests**: Tests with database and external service integration
- **Agent Tests**: Tests for multi-agent orchestration and workflows
- **API Tests**: RESTful API contract and endpoint tests
- **Performance Tests**: Load, stress, and benchmark tests
- **End-to-End Tests**: Full workflow testing
- **Security Tests**: Authentication, authorization, and vulnerability tests

## Prerequisites

### System Requirements

- Python 3.11+
- Docker and Docker Compose
- 4GB+ RAM
- 10GB+ free disk space

### Required Services

- PostgreSQL (running on port 5432)
- Redis (running on port 6379)
- Neo4j (running on ports 7474, 7687)
- Qdrant (running on ports 6333, 6334)

### Docker Services

Ensure all required services are running:

```bash
# Check status
docker ps

# Start services if needed
docker-compose -f docker-compose.production.yml up -d
```

## Environment Setup

### 1. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install test dependencies
pip install -r requirements-test.txt
```

### 2. Set Environment Variables

Copy and configure the test environment file:

```bash
cp .env.test.example .env.test
# Edit .env.test with your configuration
```

Or use the provided test configuration:

```bash
export ENVIRONMENT=testing
export DATABASE_URL=sqlite:///:memory:
export REDIS_URL=redis://localhost:6379/1
export NEO4J_URI=bolt://localhost:7687
export QDRANT_URL=http://localhost:6333
```

### 3. Create Test Database

For PostgreSQL integration tests:

```sql
CREATE DATABASE multimodal_rag_test;
GRANT ALL PRIVILEGES ON DATABASE multimodal_rag_test TO postgres;
```

### 4. Verify Environment

Run the verification script:

```bash
python verify_test_environment.py
```

This will check:
- Python package installations
- Environment variables
- Database connections
- Docker services
- File structure

## Test Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Global pytest configuration and fixtures
│   ├── factories/           # Test data factories
│   │   ├── __init__.py
│   │   ├── document_factory.py
│   │   ├── search_factory.py
│   │   └── user_factory.py
│   ├── unit/                # Unit tests (no external deps)
│   │   ├── test_services/
│   │   ├── test_agents/
│   │   └── test_utils/
│   ├── integration/         # Integration tests (database, services)
│   │   ├── test_database/
│   │   ├── test_search/
│   │   └── test_agents/
│   ├── api_contract/        # API contract tests
│   │   ├── test_v1/
│   │   └── test_v2/
│   ├── performance/         # Performance tests
│   │   ├── test_load/
│   │   ├── test_stress/
│   │   └── benchmarks/
│   ├── security/            # Security tests
│   │   ├── test_auth/
│   │   └── test_injection/
│   └── e2e/                 # End-to-end tests
├── test_config.py           # Test configuration
├── conftest.py             # Enhanced test fixtures
├── requirements-test.txt    # Test dependencies
├── .env.test              # Test environment variables
├── verify_test_environment.py  # Environment verification
└── run_tests.py           # Test runner script
```

## Running Tests

### Using the Test Runner (Recommended)

The `run_tests.py` script provides intelligent test execution:

```bash
# List available test suites
python run_tests.py --list

# Run all tests
python run_tests.py all

# Run specific suites
python run_tests.py unit integration
python run_tests.py agent --parallel --coverage
python run_tests.py performance --verbose

# Run with options
python run_tests.py unit --parallel --coverage --html-report
python run_tests.py integration --verbose --stop-on-first
```

### Using Pytest Directly

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_search_service.py

# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m agent
pytest -m performance

# Run tests in parallel
pytest -n auto

# Run with verbose output
pytest -v

# Run only failed tests
pytest --lf

# Stop on first failure
pytest -x
```

### Test Markers

Use markers to select specific test types:

- `unit`: Unit tests (no external dependencies)
- `integration`: Tests requiring database/services
- `agent`: Multi-agent specific tests
- `search`: Search functionality tests
- `api`: API endpoint tests
- `websocket`: WebSocket tests
- `performance`: Performance and load tests
- `security`: Security vulnerability tests
- `e2e`: End-to-end workflow tests
- `slow`: Tests that take longer to run
- `external`: Tests requiring external services

## Test Categories

### 1. Unit Tests

Fast, isolated tests for individual components:

```bash
# Run all unit tests
pytest tests/unit/

# Example unit test
def test_vector_search_initialization():
    service = VectorSearchService()
    assert service.client is not None
    assert service.config is not None
```

### 2. Integration Tests

Tests with real database and service integration:

```bash
# Run integration tests
pytest tests/integration/

# Example integration test
async def test_search_with_database(test_client, sample_documents):
    response = await test_client.get("/api/v2/search", params={"q": "test"})
    assert response.status_code == 200
    assert len(response.json()["results"]) > 0
```

### 3. Agent Tests

Tests for multi-agent orchestration:

```bash
# Run agent tests
pytest -m agent

# Example agent test
async def test_orchestrator_workflow(mock_search_tools):
    orchestrator = SearchOrchestrator()
    result = await orchestrator.process_query("What is AI?")
    assert result["status"] == "success"
    assert "decomposition" in result
```

### 4. API Tests

RESTful API contract tests:

```bash
# Run API tests
pytest tests/api_contract/

# Example API test
def test_search_endpoint(test_client):
    response = test_client.get("/api/v2/search?q=test")
    assert response.status_code == 200
    assert "results" in response.json()
```

### 5. Performance Tests

Load, stress, and benchmark tests:

```bash
# Run performance tests
pytest tests/performance/

# Run with benchmarking
pytest --benchmark-only

# Example performance test
def test_search_performance(benchmark):
    result = benchmark(search_service.search, "test query")
    assert len(result) > 0
```

## Mock Data and Fixtures

### Using Factories

Generate test data using factories:

```python
from tests.factories.search_factory import DocumentFactory, QueryFactory

# Create test documents
documents = DocumentFactory.create_batch(10)

# Create test query
query = QueryFactory.create_complex_query()
```

### Available Fixtures

The conftest.py provides many fixtures:

- `test_db_session`: Database session
- `test_client`: FastAPI test client
- `test_user`: Test user object
- `sample_documents`: Pre-populated test documents
- `mock_qdrant_client`: Mocked Qdrant client
- `mock_neo4j_driver`: Mocked Neo4j driver
- `knowledge_graph_service`: Service with mocked dependencies
- `vector_search_service`: Service with mocked dependencies

### Custom Fixtures

Create custom fixtures in your test files:

```python
@pytest.fixture
def custom_service(mock_qdrant_client):
    service = CustomService()
    service.client = mock_qdrant_client
    yield service
```

## Performance Testing

### Load Testing

Use the performance test framework:

```python
def test_search_load_performance():
    """Test search under load"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(search_service.search, f"query {i}")
            for i in range(100)
        ]
        results = [f.result() for f in futures]

    assert all(len(r) > 0 for r in results)
```

### Benchmarking

Use pytest-benchmark:

```python
def test_search_benchmark(benchmark):
    result = benchmark(search_service.search, "test query")
    assert result
```

### Performance Thresholds

Configure performance thresholds in test_config.py:

```python
TEST_PERFORMANCE_CONFIG = {
    "thresholds": {
        "response_time_p95": 2000,  # ms
        "response_time_p99": 5000,  # ms
        "error_rate": 1.0,          # %
        "throughput": 100           # requests/sec
    }
}
```

## Continuous Integration

### GitHub Actions

Example CI workflow:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      neo4j:
        image: neo4j:5
        env:
          NEO4J_AUTH: neo4j/password
        options: >-
          --health-cmd "cypher-shell -u neo4j -p password 'RETURN 1'"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run tests
        run: |
          python run_tests.py unit integration
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379
          NEO4J_URI: bolt://localhost:7687
          NEO4J_USER: neo4j
          NEO4J_PASSWORD: password

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./test-reports/coverage.xml
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure PostgreSQL is running
   - Check database exists: `CREATE DATABASE multimodal_rag_test;`
   - Verify connection string in .env.test

2. **Import Errors**
   - Check PYTHONPATH includes src directory
   - Run from backend directory
   - Activate virtual environment

3. **Docker Services Not Running**
   - Start services: `docker-compose up -d`
   - Check ports are not in use
   - Verify Docker is running

4. **Tests Running Slow**
   - Use SQLite for unit tests
   - Mock external services
   - Run tests in parallel: `pytest -n auto`

5. **Coverage Not Generated**
   - Install pytest-cov: `pip install pytest-cov`
   - Check src directory is in PYTHONPATH
   - Verify .coveragerc configuration

### Debug Mode

Enable debug output:

```bash
# Verbose pytest
pytest -v -s

# Show SQL queries
pytest --log-cli-level=DEBUG

# Debug individual test
pytest -xvs tests/unit/test_search.py::test_search_function
```

### Test Database Issues

Reset test database:

```bash
# Drop and recreate
dropdb multimodal_rag_test
createdb multimodal_rag_test

# Or use factory to clean
pytest --reuse-db
```

### Performance Test Issues

Increase timeouts for slow tests:

```python
@pytest.mark.timeout(300)
def test_slow_performance_test():
    pass
```

## Best Practices

1. **Write Isolated Tests**: Each test should be independent
2. **Use Descriptive Names**: Test names should describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear sections
4. **Mock External Services**: Don't rely on external APIs in tests
5. **Use Fixtures**: Reuse setup code with fixtures
6. **Test Edge Cases**: Test error conditions and edge cases
7. **Maintain Coverage**: Keep test coverage above 70%
8. **Run Tests Locally**: Ensure tests pass before pushing

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)
- [Test Coverage](https://coverage.readthedocs.io/)
- [Pytest-Benchmark](https://pytest-benchmark.readthedocs.io/)
- [DeepEval](https://docs.confident-ai.com/)