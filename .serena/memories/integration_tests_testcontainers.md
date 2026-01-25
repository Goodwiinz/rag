# Integration Tests with Testcontainers

## Overview
Integration tests using real PostgreSQL and Redis via Docker testcontainers.

## Location
`backend/tests/integration/`

## Quick Commands

```bash
# Redis tests only (fast, ~20s)
TESTCONTAINERS_RYUK_DISABLED=true ./venv/bin/python -m pytest tests/integration/services/ -v

# All integration tests (slow, ~30+ min)
TESTCONTAINERS_RYUK_DISABLED=true ./venv/bin/python -m pytest tests/integration/ -v
```

## Test Files

| File | Tests | Database | Time |
|------|-------|----------|------|
| `services/test_cache_service.py` | 12 | Redis | ~12s |
| `services/test_session_store.py` | 15 | Redis | ~15s |
| `repositories/test_document_repository.py` | 11 | PostgreSQL | ~7 min |
| `repositories/test_user_repository.py` | 11 | PostgreSQL | ~7 min |
| `repositories/test_chat_repository.py` | 15 | PostgreSQL | ~7 min |
| `flows/test_auth_flow.py` | 10 | Both | ~7 min |

**Total: ~74 tests**

## Key Technical Details

### Environment Variable Required
`TESTCONTAINERS_RYUK_DISABLED=true` - Required on macOS for Docker credential store issues

### Model Import Issue
Must import `from src.models import ab_testing` in db_session fixtures to resolve User→Experiment relationship.

### Circular FK Cleanup
AB testing tables (`ab_experiments` ↔ `ab_variants`) have circular FKs. Use:
```python
conn.execute(text("DROP SCHEMA public CASCADE"))
conn.execute(text("CREATE SCHEMA public"))
```

### Test Markers
- `@pytest.mark.requires_postgres`
- `@pytest.mark.requires_redis`
- `@pytest.mark.integration`

## PostgreSQL Slowness Reasons
1. Container startup (~30-60s)
2. 50+ tables with complex relationships
3. CASCADE cleanup for circular deps
4. Per-test table recreation

## Skipped Tests
`TestAsyncCache` (3 tests) - pytest-asyncio fixture scope issues

## Documentation
See `backend/tests/integration/README.md` for full details.
