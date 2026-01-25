# Integration Tests with Testcontainers

This directory contains integration tests that use **real databases** via Docker containers (testcontainers) instead of mocks.

## Prerequisites

```bash
# Install testcontainers
pip install testcontainers[postgres,redis]

# Docker must be running
docker ps
```

## Test Structure

```
tests/integration/
├── conftest.py                    # Shared fixtures (containers, sessions)
├── repositories/                  # PostgreSQL repository tests
│   ├── test_document_repository.py   # Document CRUD, FK constraints, cascade
│   ├── test_user_repository.py       # User model, unique email, soft delete
│   └── test_chat_repository.py       # Chat hierarchy (Workspace→Thread→Message)
├── services/                      # Redis service tests
│   ├── test_cache_service.py         # TTL, rate limiting, distributed locks
│   └── test_session_store.py         # Session management, expiration
└── flows/                         # Multi-component flow tests
    └── test_auth_flow.py             # Auth with PostgreSQL + Redis
```

## Running Tests

### Quick: Redis Tests Only (~20 seconds)

```bash
TESTCONTAINERS_RYUK_DISABLED=true ./venv/bin/python -m pytest tests/integration/services/ -v
```

### Full: All Integration Tests (~30+ minutes)

```bash
TESTCONTAINERS_RYUK_DISABLED=true ./venv/bin/python -m pytest tests/integration/ -v
```

### Specific Test File

```bash
TESTCONTAINERS_RYUK_DISABLED=true ./venv/bin/python -m pytest tests/integration/repositories/test_document_repository.py -v
```

## Environment Variable

`TESTCONTAINERS_RYUK_DISABLED=true` is required on macOS to bypass Docker credential store issues with the Ryuk container.

## Test Markers

Tests are marked for selective execution:

```python
@pytest.mark.requires_postgres  # Needs PostgreSQL container
@pytest.mark.requires_redis     # Needs Redis container
@pytest.mark.integration        # All integration tests
```

Run by marker:
```bash
pytest -m requires_redis        # Only Redis tests
pytest -m requires_postgres     # Only PostgreSQL tests
```

## Test Summary

| Test File | Tests | Time | Database |
|-----------|-------|------|----------|
| `test_cache_service.py` | 12 (+3 skipped) | ~12s | Redis |
| `test_session_store.py` | 15 | ~15s | Redis |
| `test_document_repository.py` | 11 | ~7 min | PostgreSQL |
| `test_user_repository.py` | 11 | ~7 min | PostgreSQL |
| `test_chat_repository.py` | 15 | ~7 min | PostgreSQL |
| `test_auth_flow.py` | 10 | ~7 min | PostgreSQL + Redis |

**Total: ~74 integration tests**

## Why PostgreSQL Tests Are Slow

1. **Container startup**: ~30-60 seconds to start PostgreSQL
2. **Table creation**: 50+ tables with complex relationships
3. **AB Testing models**: Circular FK dependencies require CASCADE cleanup
4. **Per-test isolation**: Tables dropped and recreated for each test

## Key Fixtures

### `postgres_container` (session-scoped)
Spins up PostgreSQL 15 Alpine container once per test session.

### `redis_container` (session-scoped)
Spins up Redis 7 Alpine container once per test session.

### `db_session` (function-scoped)
Creates SQLAlchemy session with all tables, cleans up after each test.

### `sync_redis_client` / `async_redis_client`
Redis clients for cache operations.

## Known Issues

1. **Async tests skipped**: `TestAsyncCache` tests are skipped due to pytest-asyncio fixture scope issues
2. **AB Testing circular deps**: The `ab_experiments` ↔ `ab_variants` tables have circular FKs, requiring `DROP SCHEMA CASCADE` for cleanup
3. **Model imports**: Must import `src.models.ab_testing` to resolve User→Experiment relationship

## Test Categories

### Repository Tests (PostgreSQL)
- FK constraint validation
- Unique constraint enforcement
- Cascade delete behavior
- Soft delete functionality
- Concurrent update handling
- Query filtering and ordering

### Service Tests (Redis)
- TTL expiration verification
- Rate limiting behavior
- Distributed lock acquisition
- Pub/Sub message broadcasting
- Session creation and invalidation
- Concurrent session handling

### Flow Tests (PostgreSQL + Redis)
- Full authentication flow
- Token refresh rotation
- Logout session invalidation
