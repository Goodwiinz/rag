# MVP Test Plan: Local AI RAG Integration (GOO-135)

**Feature**: Research Assistant - Phase 3 MVP
**Branch**: `004-research-assistant-feature`
**Commit**: `385f371`
**Date**: 2026-01-14
**Status**: Ready for Testing

---

## Test Environment Setup

### Prerequisites

1. **Database Migrations**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Install Dependencies**
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt

   # Frontend
   cd frontend
   npm install
   ```

3. **Start Services**
   ```bash
   # Start Docker services
   docker-compose -f docker-compose.development.yml up -d

   # Verify all services running:
   # - PostgreSQL: localhost:5432
   # - Neo4j: localhost:7687
   # - Qdrant: localhost:6333
   # - Redis: localhost:6379
   ```

4. **Start Application**
   ```bash
   # Terminal 1: Backend
   cd backend
   uvicorn src.main:app --reload --port 8000

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

5. **Access Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## Test Scenarios

### Scenario 1: Basic RAG Citation Flow (Happy Path)

**Objective**: Verify end-to-end citation persistence with local WebLLM model

**Steps**:
1. Navigate to Chat page: http://localhost:3000/chat
2. Upload a test PDF document
   - Use: Sample research paper (5-10 pages)
   - Example: ArXiv paper on machine learning
3. Wait for document processing to complete (status: "indexed")
4. Select WebLLM model:
   - Click model selector
   - Choose "Llama-3.2-1B" or "Phi-3.5-mini"
5. Enable RAG toggle:
   - Toggle should be visible near model selector
   - Verify toggle state persists on page refresh
6. Ask a question that requires document context:
   - Example: "What are the key findings in this paper?"
   - Example: "Summarize the methodology described"
7. Wait for WebLLM response (may take 30-60 seconds)

**Expected Results**:
- ✅ Response includes `[Doc 1]` citation references
- ✅ Citations are clickable links (styled differently from normal text)
- ✅ Clicking citation shows popover with:
  - Document title
  - Relevance score (%)
  - Text snippet from source
- ✅ Console shows: `[RAG] Persisted N citations` message
- ✅ No errors in browser console or terminal

**Verification**:
```bash
# Check database for persisted citations
docker exec -it rag-postgres-1 psql -U postgres -d multimodal_rag_dev

# Run query:
SELECT
    c.id,
    c.message_id,
    c.document_title,
    c.score,
    c.metadata_source,
    c.created_at
FROM citations c
ORDER BY c.created_at DESC
LIMIT 10;
```

---

### Scenario 2: Citation Persistence Verification

**Objective**: Verify citations persist across sessions

**Steps**:
1. Complete Scenario 1 (create chat with citations)
2. Note the message ID and citation count
3. Refresh the browser (Cmd+R / Ctrl+R)
4. Navigate back to the same conversation
5. Scroll to the message with citations

**Expected Results**:
- ✅ Citations still appear as clickable links
- ✅ Clicking citation still shows popover
- ✅ Citation count matches original
- ✅ No duplicate citations created

---

### Scenario 3: Multiple Document Citations

**Objective**: Verify citations from multiple documents

**Steps**:
1. Upload 2-3 different PDF documents
2. Wait for all to be indexed
3. Enable RAG toggle
4. Ask a question that spans multiple documents:
   - Example: "Compare the methodologies in these papers"
5. Review response

**Expected Results**:
- ✅ Response includes `[Doc 1]`, `[Doc 2]`, `[Doc 3]` citations
- ✅ Each citation links to correct document
- ✅ Popover shows correct document title for each
- ✅ Relevance scores differ based on retrieval

---

### Scenario 4: Model-Aware Context Configuration

**Objective**: Verify RAG context adapts to model size

**Steps**:
1. Select 1B model (Llama-3.2-1B)
   - Ask question, note response length
2. Switch to 3B model (Phi-3.5-mini)
   - Ask same question, note response length
3. Check browser console logs

**Expected Results**:
- ✅ 1B model: Max 2 documents, 600 tokens per doc
- ✅ 3B model: Max 3 documents, 1000 tokens per doc
- ✅ Console logs show: `[RAG] Using model config: ...`
- ✅ Larger models get more context and detail

---

### Scenario 5: RAG Toggle On/Off

**Objective**: Verify RAG can be disabled

**Steps**:
1. Upload document and index it
2. **With RAG enabled**:
   - Ask: "What are the key findings?"
   - Note response includes citations
3. **Disable RAG toggle**:
   - Ask same question again
   - Note response has no citations
4. **Re-enable RAG**:
   - Ask question again
   - Verify citations return

**Expected Results**:
- ✅ RAG enabled: Citations present
- ✅ RAG disabled: No citations, general response
- ✅ Toggle state persists in localStorage
- ✅ No errors when switching modes

---

### Scenario 6: No Documents Available

**Objective**: Verify graceful handling when no documents exist

**Steps**:
1. Fresh workspace with no documents
2. Enable RAG toggle
3. Ask a question

**Expected Results**:
- ✅ System responds without citations
- ✅ No errors in console
- ✅ User-friendly message: "No documents available for context"

---

### Scenario 7: Observability Logging

**Objective**: Verify structured logging is working

**Steps**:
1. Complete Scenario 1 (create citations)
2. Check backend terminal logs

**Expected Logs**:
```
INFO citations_saved message_id=... count=3 unique_docs=2 total_matches=5 duration_ms=42.15 event=citation_batch_created
DEBUG citation_created citation_id=... document_id=... score=0.85 metadata_source=rag event=individual_citation
```

**Verification**:
- ✅ Structured JSON logs with all fields
- ✅ Timing metrics present (duration_ms)
- ✅ Event types consistent
- ✅ No error logs

---

## Edge Cases to Test

### Edge Case 1: Malformed Citations
**Test**: AI response with invalid citation format `[Doc X]` where X > retrieved docs
**Expected**: Log warning, skip invalid citation, persist valid ones

### Edge Case 2: Duplicate Citations
**Test**: AI response with `[Doc 1]` mentioned multiple times
**Expected**: Only one citation record created per unique doc index

### Edge Case 3: Empty Response
**Test**: WebLLM returns response with no citations
**Expected**: No citations created, no errors, log: "no_citations_found"

### Edge Case 4: Network Failure
**Test**: Disconnect network before citation save
**Expected**: Error logged, user sees error message, can retry

### Edge Case 5: Large Document Set
**Test**: Upload 20+ documents, enable RAG
**Expected**: System retrieves top N (based on model config), not all docs

---

## Performance Benchmarks

### Target Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| RAG retrieval latency | < 2s | Time from query to context ready |
| Citation parsing | < 50ms | Parse [Doc N] from response |
| Citation persistence | < 200ms | Save all citations to DB |
| Popover render | < 100ms | Show citation details |
| Page load with citations | < 1s | Render message with 10 citations |

### How to Measure

1. **Browser DevTools**:
   - Network tab: API call durations
   - Performance tab: Component render times
   - Console: `[RAG]` log timestamps

2. **Backend Logs**:
   - Look for `duration_ms` in structured logs
   - Track `citations_saved` event timing

3. **Example Timing Log**:
   ```
   [RAG] Retrieval started: 14:23:45.100
   [RAG] Retrieved 3 documents: 14:23:46.850 (1750ms)
   [RAG] Persisted 5 citations: 14:23:47.120 (270ms)
   ```

---

## Acceptance Criteria Checklist

Based on GOO-135 specification:

- [ ] **AC1**: Upload a PDF document
  - Verify document appears in list
  - Status transitions to "indexed"

- [ ] **AC2**: Select Llama-3.2-1B model
  - Model selector shows available WebLLM models
  - Selection persists across page loads

- [ ] **AC3**: Enable RAG toggle
  - Toggle switch visible and functional
  - State persists to localStorage

- [ ] **AC4**: Ask "What are the key findings?"
  - Question submitted successfully
  - WebLLM generates response

- [ ] **AC5**: Verify response includes `[Doc N]` citations
  - Citations present in response text
  - Format matches pattern: `[Doc 1]`, `[Doc 2]`, etc.

- [ ] **AC6**: Click citation link shows snippet popover
  - Citation is clickable (styled as link)
  - Popover appears on click
  - Popover contains: title, score, snippet

- [ ] **AC7**: Citations are persisted to database
  - Database query shows citation records
  - message_id matches chat message
  - document_id links to uploaded document

- [ ] **AC8**: Citations appear on page refresh
  - Refresh browser
  - Navigate back to conversation
  - Citations still rendered and clickable

---

## Known Limitations (Document for Users)

1. **WebGPU Requirement**:
   - Requires Chrome 113+, Edge 113+, or Firefox 121+
   - Safari not yet supported

2. **Model Size vs RAM**:
   - 1B models: 4GB+ RAM required
   - 3B models: 8GB+ RAM required
   - 7B models: 16GB+ RAM required

3. **First Inference Delay**:
   - Model download: 500MB-2GB (one-time, cached)
   - First inference: 30-60s (includes model load)
   - Subsequent: 5-15s per response

4. **Citation Format Dependency**:
   - System expects AI to use `[Doc N]` format
   - Manual citation cleanup if format differs

5. **Retrieval Limits**:
   - Max documents per query: 2-8 (based on model size)
   - Token limits prevent unlimited context

---

## Rollback Plan

If critical issues found during testing:

```bash
# Revert to previous stable commit
git checkout develop
git pull origin develop

# Or revert specific commit
git revert 385f371

# Restart services
docker-compose -f docker-compose.development.yml restart backend frontend
```

---

## Success Criteria

**Testing is successful if**:
- ✅ All 8 acceptance criteria pass
- ✅ All 5 main scenarios work without errors
- ✅ Performance within 20% of targets
- ✅ No critical console errors or backend crashes
- ✅ Observability logs show correct data

**Testing requires fixes if**:
- ❌ Citations not persisting to database
- ❌ Popover not rendering or shows wrong data
- ❌ RAG toggle not working
- ❌ Critical errors in logs
- ❌ Performance > 2x targets

---

## Test Report Template

After testing, document results:

```markdown
# MVP Test Results: GOO-135

**Tester**: [Your Name]
**Date**: [YYYY-MM-DD]
**Environment**: Development
**Browser**: Chrome 131 / Firefox 121 / Edge 131

## Scenarios Passed: X/5
- [x] Scenario 1: Basic RAG Citation Flow
- [ ] Scenario 2: Citation Persistence
- ...

## Acceptance Criteria: X/8
- [x] AC1: Upload PDF
- [x] AC2: Select model
- ...

## Issues Found
1. [High/Medium/Low] Issue description
   - Steps to reproduce
   - Expected vs actual
   - Screenshot/logs

## Performance
- RAG retrieval: XXXms (target: <2000ms)
- Citation persistence: XXms (target: <200ms)

## Recommendations
- [ ] Ready to deploy
- [ ] Needs fixes before deploy
- [ ] Blockers: [list issues]
```

---

## Next Steps After Testing

1. **If testing passes**:
   - Create PR: `004-research-assistant-feature` → `develop`
   - Update Linear: GOO-135 → "Done"
   - Deploy to staging environment
   - User acceptance testing

2. **If issues found**:
   - Create bug tickets in Linear
   - Prioritize critical vs nice-to-have
   - Fix and re-test
   - Update test plan with new scenarios

3. **Documentation**:
   - Update user guide with citation workflow
   - Add troubleshooting section
   - Document WebGPU requirements
