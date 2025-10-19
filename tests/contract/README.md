# Contract Tests for Multimodal Enterprise RAG System Evaluation Platform

This directory contains comprehensive contract tests for the Multimodal Enterprise RAG System evaluation platform. These tests ensure API contracts are stable and reliable for frontend consumption by validating request/response schemas, authentication flows, error handling, and performance characteristics.

## 🎯 Test Coverage

### Evaluation Service API Contracts
- **POST /api/v1/evaluation/jobs** - Create evaluation jobs
- **POST /api/v1/evaluation/jobs/batch** - Create batch evaluation jobs
- **POST /api/v1/evaluation/real-time** - Real-time evaluation endpoint
- **GET /api/v1/evaluation/jobs/{id}** - Get evaluation job details
- **GET /api/v1/evaluation/jobs** - List evaluation jobs
- **GET /api/v1/evaluation/jobs/{id}/metrics** - Get evaluation metrics
- **GET /api/v1/evaluation/metrics/summary** - Get metrics summary
- **POST /api/v1/evaluation/comparisons** - Create evaluation comparisons
- **GET /api/v1/evaluation/comparisons** - List evaluation comparisons

### Authentication & Authorization Contracts
- JWT token validation and expiration handling
- Role-based access control (RBAC)
- Organization-level resource scoping
- API key authentication (if supported)
- Token tampering detection
- Concurrent request authentication

### Error Response Validation
- **400 Bad Request** - Validation errors
- **401 Unauthorized** - Authentication failures
- **403 Forbidden** - Authorization failures
- **404 Not Found** - Resource not found
- **429 Too Many Requests** - Rate limiting
- **500 Internal Server Error** - Server errors
- Error response schema consistency
- Security information leakage prevention

### Load Testing Scenarios
- Concurrent evaluation job creation
- Real-time evaluation throughput
- Sustained metrics retrieval load
- Batch evaluation processing
- Mixed workload testing
- Stress testing for maximum capacity

## 📁 Directory Structure

```
tests/contract/
├── conftest.py                          # Base configuration and fixtures
├── run_contract_tests.py               # Test runner script
├── README.md                           # This documentation
├── evaluation/
│   ├── test_evaluation_jobs_api.py     # Job creation contract tests
│   ├── test_batch_evaluation_api.py    # Batch evaluation tests
│   ├── test_realtime_evaluation_api.py # Real-time evaluation tests
│   ├── test_job_retrieval_api.py      # Job retrieval tests
│   ├── test_evaluation_metrics_api.py  # Metrics retrieval tests
│   ├── test_evaluation_comparisons_api.py # Comparison tests
│   ├── test_error_response_contract.py # Error validation tests
│   └── fixtures/
│       └── data_generators.py         # Test data generators
├── auth/
│   └── test_evaluation_auth_contract.py # Authentication tests
└── load/
    └── test_evaluation_load.py         # Load testing scenarios
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pytest with required plugins
- httpx for async HTTP testing
- faker for test data generation

### Installation
```bash
# Install dependencies
pip install pytest pytest-asyncio pytest-html httpx faker

# Install test dependencies
pip install -r requirements-test.txt
```

### Running Tests

#### Using the Test Runner (Recommended)
```bash
# Run all contract tests
python tests/contract/run_contract_tests.py

# Run only evaluation API tests
python tests/contract/run_contract_tests.py --type evaluation

# Run fast tests (exclude load tests)
python tests/contract/run_contract_tests.py --type fast

# Run with verbose output
python tests/contract/run_contract_tests.py --verbose

# Generate coverage report
python tests/contract/run_contract_tests.py --coverage

# Save results to JSON
python tests/contract/run_contract_tests.py --save-results
```

#### Using pytest Directly
```bash
# Run all contract tests
pytest tests/contract/ -m contract

# Run evaluation contract tests only
pytest tests/contract/evaluation/ -m evaluation_contract

# Run authentication tests
pytest tests/contract/auth/ -m auth_contract

# Run load tests
pytest tests/contract/load/ -m load_test

# Run with HTML report
pytest tests/contract/ --html=contract_test_report.html

# Run specific test file
pytest tests/contract/evaluation/test_evaluation_jobs_api.py -v
```

## 📊 Test Categories

### 1. Contract Tests (`@pytest.mark.contract`)
Validate that API endpoints adhere to defined contracts:
- Request/response schema validation
- Data type consistency
- Required field validation
- Enum value validation

### 2. Evaluation Contract Tests (`@pytest.mark.evaluation_contract`)
Focus specifically on evaluation API endpoints:
- Job creation and management
- Metrics retrieval
- Real-time evaluation
- Batch processing

### 3. Authentication Contract Tests (`@pytest.mark.auth_contract`)
Test authentication and authorization:
- JWT token validation
- Role-based access control
- Organization scoping
- Token expiration

### 4. Load Tests (`@pytest.mark.load_test`)
Performance and load testing:
- Concurrent request handling
- Response time thresholds
- Throughput measurements
- Stress testing

### 5. Error Contract Tests (`@pytest.mark.error_contract`)
Error response validation:
- Consistent error schemas
- Proper HTTP status codes
- Security of error messages
- Rate limiting responses

## 🔧 Configuration

### Environment Variables
```bash
# Test environment
export ENVIRONMENT=testing
export DEBUG=true
export LOG_LEVEL=INFO

# Database
export DATABASE_URL=sqlite:///:memory:

# External services (mocked)
export NEO4J_URI=bolt://localhost:7687
export QDRANT_URL=http://localhost:6333
export REDIS_URL=redis://localhost:6379/1

# Authentication
export OPENAI_API_KEY=test-key
export ANTHROPIC_API_KEY=test-key
```

### Performance Thresholds
Load tests use the following performance thresholds:
- **P95 Response Time**: ≤ 2.0 seconds
- **P99 Response Time**: ≤ 5.0 seconds
- **Error Rate**: ≤ 5%
- **Minimum Throughput**: ≥ 5 RPS

## 📈 Test Data Generation

The test suite includes comprehensive data generators in `evaluation/fixtures/data_generators.py`:

### EvaluationDataGenerator
- Realistic evaluation requests
- Batch evaluation data
- Real-time evaluation scenarios
- Comparison requests

### JobDataGenerator
- Evaluation job records
- Job summary responses
- Different job statuses and types

### MetricDataGenerator
- Evaluation metric records
- Metrics responses
- Summary statistics
- Different metric types

## 🎯 Test Reports

### HTML Reports
Generated automatically when using the test runner:
```bash
python tests/contract/run_contract_tests.py
# Output: test_reports/contract_test_report_YYYYMMDD_HHMMSS.html
```

### JUnit XML Reports
For CI/CD integration:
```bash
python tests/contract/run_contract_tests.py
# Output: test_reports/contract_test_junit_YYYYMMDD_HHMMSS.xml
```

### Coverage Reports
When `--coverage` flag is used:
```bash
python tests/contract/run_contract_tests.py --coverage
# Output: test_reports/coverage/
```

## 🔄 Continuous Integration

### GitHub Actions Example
```yaml
name: Contract Tests
on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements-test.txt
    - name: Run contract tests
      run: |
        python tests/contract/run_contract_tests.py --type fast --save-results
    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: contract-test-results
        path: test_reports/
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Ensure Python path includes project root
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
```

#### 2. Database Connection Errors
```bash
# Ensure test database is configured
export DATABASE_URL=sqlite:///:memory:
```

#### 3. Authentication Test Failures
```bash
# Check JWT secret configuration
export SECRET_KEY=test-secret-key-for-tests
```

#### 4. Load Test Timeouts
```bash
# Increase timeout for slow tests
pytest tests/contract/load/ --timeout=300
```

### Debug Mode
Run tests with extra debugging:
```bash
python tests/contract/run_contract_tests.py --verbose --coverage
```

### Selective Test Execution
Run specific test categories:
```bash
# Only fast contract tests
pytest tests/contract/ -m "contract and not slow and not load_test"

# Only authentication tests
pytest tests/contract/ -m "auth_contract"

# Only error handling tests
pytest tests/contract/ -m "error_contract"
```

## 📚 Best Practices

### 1. Test Organization
- Group related tests in appropriate modules
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

### 2. Data Management
- Use factories and generators for test data
- Avoid hardcoded test values
- Ensure data isolation between tests

### 3. Error Handling
- Test both success and failure scenarios
- Validate error response schemas
- Check for security information leakage

### 4. Performance Testing
- Use realistic data volumes
- Test under different load conditions
- Monitor system resources during tests

### 5. Maintenance
- Keep tests updated with API changes
- Review and refactor test code regularly
- Document test purpose and scenarios

## 🤝 Contributing

When adding new contract tests:

1. **Follow naming conventions**: Use descriptive test method names
2. **Use appropriate markers**: Apply relevant pytest markers
3. **Include documentation**: Add docstrings explaining test purpose
4. **Validate contracts**: Ensure request/response schemas are validated
5. **Test edge cases**: Include boundary conditions and error scenarios
6. **Keep tests isolated**: Tests should not depend on each other

## 📄 License

These contract tests are part of the Multimodal Enterprise RAG System and follow the same license terms as the main project.

---

## 🔗 Related Documentation

- [Main API Documentation](../../docs/api.md)
- [Evaluation System Guide](../../docs/evaluation.md)
- [Authentication Guide](../../docs/authentication.md)
- [Performance Testing Guide](../../docs/performance.md)