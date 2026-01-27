# GOO-151: Scaffolding Test Fix Tasks

Parent Issue: GOO-151 - Fix scaffolding tests - move working tests back to main test directories

## Analysis Summary

21 test files were moved to `backend/tests/scaffolding/` due to failures. Analysis reveals:
- **Cache modules are COMPLETE** - No missing exports (contrary to initial assumption)
- **Mock infrastructure is robust** - `backend/tests/mocks/services.py` has comprehensive implementations
- **5 unit service tests should pass as-is** - They use mocks only, no real dependencies

## Tasks to Create as Sub-issues

### Task 1: Verify Unit Service Tests (HIGH - Quick Win)
**Title:** `test: Verify unit service tests in scaffolding pass`
**Priority:** 2 (High)
**Labels:** `testing`, `quick-win`
**Description:**
```
Run the 5 unit service tests that use only mocks to verify they pass:
- test_auth_service.py
- test_chat_service.py  
- test_knowledge_graph_service.py
- test_hybrid_search_service.py
- test_vector_store_service.py

These tests are self-contained with proper mock infrastructure.

Acceptance Criteria:
- [ ] Run tests in Docker environment with pytest
- [ ] Document any failures
- [ ] Move passing tests back to `tests/unit/services/`
```

### Task 2: Fix Integration Test Patterns
**Title:** `fix: Update integration tests for API compatibility`
**Priority:** 3 (Normal)
**Labels:** `testing`, `api`
**Description:**
```
Update integration tests to match current API patterns:
- test_api_endpoints.py
- test_search_api.py
- test_realtime_search.py

Changes needed:
- Update response format expectations
- Align with current router paths
- Use proper test fixtures

Acceptance Criteria:
- [ ] Tests use TestClient properly
- [ ] Response schemas match current API
- [ ] Move passing tests to `tests/integration/`
```

### Task 3: Fix Root-Level Tests
**Title:** `fix: Update root-level scaffolding tests`
**Priority:** 3 (Normal)  
**Labels:** `testing`
**Description:**
```
Fix tests in scaffolding root directory:
- test_analytics_cache.py - Uses existing cache module (exports exist)
- test_auth.py - JWT auth tests
- test_files.py - File upload tests
- test_chat_conversation.py - Chat flow tests
- test_message_ordering.py - Message ordering tests

Acceptance Criteria:
- [ ] Each test file runs without import errors
- [ ] Mock dependencies properly injected
- [ ] Move passing tests to appropriate directories
```

### Task 4: Fix Search Service Tests
**Title:** `fix: Update search service unit tests`
**Priority:** 3 (Normal)
**Labels:** `testing`, `search`
**Description:**
```
Fix search-related tests:
- unit/services/test_search_service.py
- test_document_search.py
- test_document_processing.py

Use MockFulltextSearchService, MockVectorSearchService from mocks/services.py

Acceptance Criteria:
- [ ] Tests use mock search services
- [ ] No real database connections required
- [ ] Move passing tests to `tests/unit/services/`
```

### Task 5: Document Test Environment Setup
**Title:** `docs: Document test environment requirements`
**Priority:** 4 (Low)
**Labels:** `documentation`, `testing`
**Description:**
```
Create documentation for running scaffolding tests:
- Required pytest plugins
- Docker vs local environment setup
- Mock injection patterns
- Test categorization (unit vs integration)

Location: docs/testing/scaffolding-tests.md
```

## Blocking Information

- pytest not available in system Python 3.14
- Need to run tests in Docker environment or virtualenv
- Command: `docker-compose exec backend pytest tests/scaffolding/ -v`

## Files Reference

### Test Files (21 total)
Root: test_analytics_cache.py, test_auth.py, test_files.py, test_chat_conversation.py, test_message_ordering.py
Integration: test_api_endpoints.py, test_search_api.py, test_realtime_search.py
Unit/Services: test_auth_service.py, test_chat_service.py, test_knowledge_graph_service.py, test_hybrid_search_service.py, test_search_service.py, test_vector_store_service.py, test_agent_service.py, test_document_service.py, test_file_upload_service.py

### Mock Infrastructure
- `backend/tests/mocks/services.py` - All mock implementations (876 lines)
- MockAsyncSession, MockResult, MockScalarsResult
- MockNeo4jDriver, MockNeo4jSession
- MockRedisClient
- MockFulltextSearchService, MockVectorSearchService, MockGraphSearchService

### Cache Modules (COMPLETE - No fixes needed)
- `backend/src/cache/analytics_cache.py` - Has all exports
- `backend/src/cache/cache_keys.py` - Has CacheKeyBuilder, CacheKeyPattern, CacheKeyValidator

## Recommended Approach

1. **First**: Run unit service tests in Docker - expect 5 to pass immediately
2. **Second**: Fix integration tests with API alignment
3. **Third**: Root-level tests
4. **Fourth**: Search service tests
5. **Finally**: Document everything

Created: 2026-01-27
