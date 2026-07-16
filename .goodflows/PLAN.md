<task type="review">
  <name>Test Bulk Thread Operations and Automatic Summarization (GOO-52, GOO-48)</name>

  <context>
    <why>Ensure the bulk operations feature and thread summarization are fully tested before merging to develop. Critical for production readiness.</why>
    <session>session_1768253884945_d54a412f</session>
  </context>

  <scope>
    <files>
      <file action="modify">backend/src/api/threads.py</file>
      <file action="modify">backend/src/services/thread_summarization_service.py</file>
      <file action="modify">backend/src/services/chat_service.py</file>
      <file action="modify">backend/src/tasks/summarize_thread_task.py</file>
      <file action="create">tests/unit/test_bulk_thread_operations.py</file>
      <file action="create">tests/unit/test_thread_summarization.py</file>
      <file action="create">tests/integration/test_bulk_thread_api.py</file>
    </files>
  </scope>

  <action>
    ## Phase 1: Unit Tests for Bulk Thread Service Methods

### 1.1 ChatService.bulk_update_threads() Tests
- Test bulk resolve with valid thread IDs (happy path)
- Test bulk archive with valid thread IDs
- Test partial success (some threads exist, some don&apos;t)
- Test empty thread_ids list (should fail validation)
- Test max 100 thread limit enforcement
- Test authorization: user can only update own threads
- Test transaction rollback on error

### 1.2 ChatService.bulk_delete_threads() Tests
- Test bulk delete with valid thread IDs
- Test partial delete (some succeed, some fail)
- Test cascade: messages deleted with threads
- Test currentThreadId cleared if deleted

## Phase 2: Unit Tests for Thread Summarization Service

### 2.1 ThreadSummarizationService Tests
- Test should_summarize() with &lt; 3 messages (should return False)
- Test should_summarize() with &gt;= 3 messages (should return True)
- Test rate limiting via Redis (5 min cooldown)
- Test _format_messages_for_prompt() truncation at 2000 chars
- Test _clean_summary() length enforcement (MAX_SUMMARY_LENGTH)
- Test _generate_fallback_summary() when no LLM available

### 2.2 LLM Provider Tests (with mocks)
- Test _generate_with_openai() success path
- Test _generate_with_openai() timeout handling
- Test _generate_with_anthropic() fallback when OpenAI fails
- Test fallback to _generate_fallback_summary() when both LLMs fail

## Phase 3: Integration Tests for Bulk API Endpoints

### 3.1 POST /threads/bulk/resolve Tests
- Test 200 response with valid request
- Test response schema matches BulkThreadResponse
- Test WebSocket broadcast sent for bulk updates
- Test 422 for invalid thread_ids format
- Test 401 for unauthenticated requests
- Test cross-user authorization (can&apos;t resolve others&apos; threads)

### 3.2 POST /threads/bulk/archive Tests
- Test 200 response with partial success
- Test archived threads not in active list
- Test archived threads still accessible by ID

### 3.3 DELETE /threads/bulk Tests
- Test 200 response with full success
- Test cascade delete of messages
- Test confirmation dialog shown in UI
- Test undo functionality (if implemented)

## Phase 4: Celery Task Tests

### 4.1 summarize_thread_task Tests
- Test task execution with valid thread_id
- Test auto-retry on failure (max 3 retries)
- Test force=True bypasses rate limit
- Test on_success callback logging
- Test on_failure callback logging

### 4.2 batch_summarize_threads_task Tests
- Test batch processing results aggregation
- Test partial success handling

## Phase 5: Frontend Component Tests (if time permits)

### 5.1 Chat Store Tests
- Test toggleSelectMode() action
- Test toggleThreadSelection() add/remove
- Test selectAllThreads() selects current conversation threads
- Test clearSelection() clears selectedThreadIds
- Test bulkResolveThreads() updates local state
- Test bulkDeleteThreads() clears currentThreadId if deleted

### 5.2 ConversationSidebar Tests
- Test checkbox visibility in select mode
- Test bulk action toolbar appears when items selected
- Test confirmation dialog for bulk delete
  </action>

  <verify>
    <check type="command">cd backend &amp;&amp; python -m pytest tests/unit/test_bulk_thread_operations.py -v</check>
    <check type="command">cd backend &amp;&amp; python -m pytest tests/unit/test_thread_summarization.py -v</check>
    <check type="command">cd backend &amp;&amp; python -m pytest tests/integration/test_bulk_thread_api.py -v</check>
    <check type="command">cd backend &amp;&amp; python -m mypy src/api/threads.py src/services/thread_summarization_service.py --strict</check>
  </verify>

  <done>
    All test suites pass with &gt;80% coverage for bulk operations and summarization code. MyPy type checking passes. No regressions in existing thread tests.
  </done>

  <tracking>
    <goodflows>true</goodflows>
  </tracking>
</task>