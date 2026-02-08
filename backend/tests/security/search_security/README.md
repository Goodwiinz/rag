# Search Endpoint Security Test Suite

This directory contains comprehensive security tests for all search endpoints in the RAG system.

## Test Categories

1. **Input Validation Tests** (`test_input_validation.py`)
   - Query parameter validation
   - Payload size limits
   - Character encoding tests
   - Parameter type validation

2. **Authentication and Authorization Tests** (`test_auth_security.py`)
   - JWT token validation
   - API key authentication
   - Role-based access control
   - Organization isolation
   - User permissions

3. **SQL Injection Prevention Tests** (`test_sql_injection.py`)
   - Query parameter injection
   - Filter parameter injection
   - Sort parameter injection
   - Nested query injection

4. **XSS Protection Tests** (`test_xss_protection.py`)
   - Script injection in queries
   - HTML entity encoding
   - Response sanitization
   - JSON response security

5. **Rate Limiting Tests** (`test_rate_limiting.py`)
   - Request frequency limits
   - Per-user rate limiting
   - Burst protection
   - API key rate limiting

6. **Error Handling and Logging Tests** (`test_error_handling.py`)
   - Information disclosure prevention
   - Error message sanitization
   - Security event logging
   - Audit trail verification

## Search Endpoints Tested

- `POST /search/` - Main search endpoint
- `POST /search/hybrid` - Hybrid search
- `GET /search/suggestions` - Search suggestions
- `GET /search/history` - Search history
- `POST /search/history` - Add search history
- `DELETE /search/history` - Clear search history

## Running the Tests

```bash
# Run all search security tests
pytest tests/security/search_security/ -v

# Run specific category
pytest tests/security/search_security/test_input_validation.py -v

# Run with coverage
pytest tests/security/search_security/ --cov=src/api/search --cov-report=html
```

## Test Configuration

The tests use specialized fixtures and configurations to simulate various attack scenarios safely.
See `conftest.py` for test setup and teardown procedures.