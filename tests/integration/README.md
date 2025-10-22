# Integration Test Suite for Knowledge Graph Analytics Dashboard

This comprehensive integration test suite validates the entire Knowledge Graph Analytics Dashboard system, ensuring API contracts, data flow, real-time communication, security, and performance meet enterprise standards.

## Overview

The integration tests are organized into the following categories:

### 1. API Contract Tests (`test_api_contracts.py`)
Validates all endpoints against the OpenAPI specification in `/docs/api/knowledge-graph-analytics-dashboard.yaml`.

**Key Features:**
- OpenAPI schema compliance validation
- Parameter validation testing
- Response format verification
- Error response contract testing
- Pagination validation

### 2. Frontend-Backend Integration Tests (`test_frontend_backend_integration.py`)
Tests data flow between Next.js frontend components and FastAPI backend services.

**Key Features:**
- Complete CRUD operation flows
- Widget data refresh mechanisms
- Report generation workflows
- Graph analytics integration
- Real-time data processing
- Concurrent request handling

### 3. WebSocket Integration Tests (`test_websocket_integration.py`)
Validates real-time communication between frontend and backend via WebSocket connections.

**Key Features:**
- Connection establishment and authentication
- Subscription management
- Real-time metrics updates
- Alert notifications
- Heartbeat/ping-pong mechanisms
- Connection lifecycle management

### 4. Authentication & Authorization Tests (`test_authentication_authorization.py`)
Tests security controls, role-based access, and permission validation.

**Key Features:**
- JWT token authentication
- Role-based access control (RBAC)
- Organization isolation
- WebSocket authentication
- Rate limiting by role
- Session management

### 5. Data Validation Tests (`test_data_validation.py`)
Tests data integrity, validation, and consistency across the full stack.

**Key Features:**
- Input validation on create/update operations
- Data type validation
- UUID format validation
- JSON structure validation
- Referential integrity
- Data sanitization

### 6. Error Handling Tests (`test_error_handling.py`)
Tests error scenarios, graceful degradation, and recovery mechanisms.

**Key Features:**
- Standardized error response formats
- Timeout error handling
- Rate limiting recovery
- Circuit breaker patterns
- Graceful degradation
- Bulk operation error handling

### 7. Performance Integration Tests (`test_performance_integration.py`)
Tests response times, throughput, and system performance under load.

**Key Features:**
- API response time validation
- Concurrent request handling
- Memory usage monitoring
- Large response handling
- Database query performance
- Cache performance testing
- Stress testing

### 8. Multi-tenant Isolation Tests (`test_multitenant_isolation.py`)
Tests data separation and isolation between organizations.

**Key Features:**
- Organization data isolation
- Cross-organization access prevention
- User session isolation
- Concurrent organization operations
- Database constraint validation
- WebSocket isolation

## Test Infrastructure

### Configuration (`conftest.py`)
Provides comprehensive test infrastructure including:

- **Docker Containers**: PostgreSQL and Redis containers for isolated testing
- **Mock Services**: Frontend stores and WebSocket services
- **Authentication**: JWT token generation and validation
- **Database Management**: Test database setup, migrations, and cleanup
- **Performance Monitoring**: Memory, CPU, and response time tracking

### Key Fixtures

- `postgres_container`: PostgreSQL test container
- `redis_container`: Redis test container
- `test_db_session`: Database session with transaction rollback
- `api_client`: HTTP client for API testing
- `websocket_client`: WebSocket client for real-time testing
- `sample_organization`: Test organization data
- `sample_user`: Test user with roles and permissions
- `performance_metrics`: Performance tracking utilities

## Running Tests

### Prerequisites

1. **Docker**: Required for test database and Redis containers
2. **Python Dependencies**: Install from `requirements.txt`
3. **Node.js Dependencies**: Install in `frontend/` directory

### Environment Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd frontend && npm install

# Start Docker services (if not already running)
docker-compose up -d
```

### Running Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test category
pytest tests/integration/test_api_contracts.py -v
pytest tests/integration/test_websocket_integration.py -v

# Run with performance markers
pytest tests/integration/ -m performance -v

# Run with coverage
pytest tests/integration/ --cov=src --cov-report=html

# Run in parallel (if pytest-xdist is installed)
pytest tests/integration/ -n auto
```

### Test Markers

Use pytest markers to run specific test categories:

```bash
# API contract tests
pytest tests/integration/ -m api_contract

# Authentication tests
pytest tests/integration/ -m auth

# WebSocket tests
pytest tests/integration/ -m websocket

# Performance tests
pytest tests/integration/ -m performance

# Multi-tenant tests
pytest tests/integration/ -m multitenant
```

## Test Data and Fixtures

### Sample Organizations
- Organization Alpha, Beta, and Gamma for multi-tenant testing
- Different configurations and settings per organization

### Sample Users
- Admin, Analyst, and Viewer roles
- Cross-organization user scenarios

### Sample Data
- Dashboard configurations with widgets
- Report definitions and executions
- Alert rules and notifications
- Metrics and analytics data

## Performance Targets

The tests validate the following performance targets:

### API Response Times
- Real-time metrics: < 2 seconds
- Dashboard listing: < 1 second
- Graph analytics: < 5 seconds
- Report listing: < 1.5 seconds

### Concurrent Load
- 10 concurrent users, 5 requests each
- 95% success rate minimum
- Average response time < 3 seconds
- P95 response time < 5 seconds

### Memory Usage
- < 100MB growth during sustained load
- < 500MB total memory usage
- Proper cleanup after operations

## Database Schema Validation

Tests verify database constraints and isolation:

### Foreign Key Constraints
- Organization-scoped data relationships
- Prevent cross-organization data references

### Row-Level Security
- Organization-based data filtering
- User permission validation

### Data Integrity
- UUID validation for foreign keys
- Required field constraints
- Data type validation

## Security Testing

### Authentication
- JWT token validation
- Token expiry handling
- Refresh token mechanisms

### Authorization
- Role-based access control
- Resource-level permissions
- Cross-organization access prevention

### Data Security
- Input sanitization
- SQL injection prevention
- XSS protection

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run integration tests
      run: |
        pytest tests/integration/ -v --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Docker Container Issues**
   ```bash
   # Check container status
   docker-compose ps

   # Restart services
   docker-compose restart

   # Check logs
   docker-compose logs postgres
   docker-compose logs redis
   ```

2. **Database Connection Issues**
   ```bash
   # Verify database is ready
   docker-compose exec postgres pg_isready

   # Check connection
   docker-compose exec postgres psql -U postgres -d test_analytics
   ```

3. **Port Conflicts**
   ```bash
   # Check what's using ports
   lsof -i :5432  # PostgreSQL
   lsof -i :6379  # Redis
   lsof -i :8000  # API Server
   ```

4. **Test Timeouts**
   - Increase timeout values in `conftest.py`
   - Check system resources
   - Verify Docker daemon performance

### Debug Mode

Run tests with additional debugging:

```bash
# Increase verbosity
pytest tests/integration/ -v -s

# Stop on first failure
pytest tests/integration/ -x

# Run specific test with debugging
pytest tests/integration/test_api_contracts.py::TestAPIContracts::test_realtime_metrics_endpoint_contract -v -s
```

## Contributing

When adding new integration tests:

1. **Follow Naming Conventions**: Use descriptive test names that explain the scenario
2. **Use Test Markers**: Apply appropriate markers (`@pytest.mark.integration`, `@pytest.mark.performance`, etc.)
3. **Include Fixtures**: Use existing fixtures or create new ones following the established patterns
4. **Add Documentation**: Document complex scenarios and expected behaviors
5. **Test Error Cases**: Include both success and failure scenarios
6. **Performance Validation**: Add performance assertions where applicable

## Best Practices

### Test Organization
- Group related tests in classes
- Use descriptive test method names
- Separate setup, execution, and assertion phases

### Data Management
- Use fixtures for consistent test data
- Clean up resources after tests
- Avoid dependencies between tests

### Error Handling
- Test both success and failure scenarios
- Validate error messages and formats
- Test recovery mechanisms

### Performance Testing
- Measure actual response times
- Monitor resource usage
- Test under realistic load conditions

This comprehensive integration test suite ensures the Knowledge Graph Analytics Dashboard meets enterprise requirements for reliability, security, performance, and maintainability.