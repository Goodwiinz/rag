# Integration Test Fixture Investigation

**Date**: 2026-01-27
**Status**: ⚠️ Partially Fixed - Fixtures created but async engine issue remains
**Related**: test_project_chat_api.py integration tests

## Problem Summary

All 9 integration tests in `test_project_chat_api.py` were failing with "fixture not found" errors.

## Root Cause

The integration test file referenced fixtures that didn't exist:
- `async_client` - Async HTTP client for API testing
- `test_user` - Test user model
- `test_workspace` - Test workspace model
- `test_project` - Test project/collection model
- `test_thread` - Test thread model
- `test_project_thread` - Test project-thread link model
- `other_user`, `other_workspace` - For isolation testing

## Fixes Applied

### 1. Created Missing Fixtures

Added comprehensive fixtures to `tests/integration/conftest.py`:

```python
@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create test database with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_client(test_db):
    """Create async HTTP client with test database override."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession):
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hashed_password_123",
        role=UserRole.USER,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


# ... Similar fixtures for workspace, project, thread, etc.
```

### 2. Added pytest-asyncio Configuration

Updated `tests/pytest.ini`:

```ini
[tool:pytest]
asyncio_mode = auto
# ... other config
```

## Remaining Issue

⚠️ **Async Engine Context Manager Error**

Tests still fail during fixture setup at:
```
tests/integration/conftest.py:319: in test_db
    async with engine.begin() as conn:
```

Error traceback shows issue in SQLAlchemy async engine initialization.

## Possible Causes

1. **SQLAlchemy async engine bug** with SQLite + aiosqlite
2. **Fixture scope issue** - may need different scope strategy
3. **Missing await** in fixture chain
4. **SQLite async driver issue** - aiosqlite may not support all features

## Next Steps

### Option 1: Use Sync SQLite (Simpler)
```python
@pytest.fixture(scope="function")
def test_db():
    """Create test database with all tables (synchronous)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
```

### Option 2: Use Real PostgreSQL via Testcontainers
```python
@pytest.fixture(scope="function")
def test_db(postgres_container):
    """Use real PostgreSQL container for tests."""
    engine = create_engine(postgres_container["url"])
    # ... rest of setup
```

### Option 3: Fix Async SQLite Engine
- Investigate SQLAlchemy + aiosqlite compatibility
- Check if engine.begin() is the correct pattern
- May need to use `async with engine.connect() as conn` instead

## Files Modified

1. `backend/tests/integration/conftest.py` - Added all fixtures
2. `backend/tests/pytest.ini` - Added `asyncio_mode = auto`

## Testing Commands

```bash
# Run single test
pytest tests/integration/test_project_chat_api.py::TestProjectChatIntegration::test_start_chat_from_project -v

# Check fixture availability
pytest tests/integration/test_project_chat_api.py --fixtures | grep "test_user\|async_client"

# Run all project chat tests (when fixed)
pytest tests/integration/test_project_chat_api.py -v
```

## Recommendations

1. **Quick Fix**: Use synchronous SQLite for integration tests
   - Simpler, more reliable
   - Most integration tests don't need async DB

2. **Better Fix**: Use testcontainers with real PostgreSQL
   - Tests real database behavior
   - Better matches production
   - Already have `postgres_container` fixture

3. **Best Practice**: Mock HTTP layer instead of database
   - Faster tests
   - Less setup complexity
   - Focus on API contract, not DB

## Related Documentation

- `.serena/memories/projectthread_persistence_bug_fix.md` - Unit test fixes
- `backend/tests/integration/conftest.py` - Integration test fixtures
- SQLAlchemy async: https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html
