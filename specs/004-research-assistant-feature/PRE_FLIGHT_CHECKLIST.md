# Pre-Flight Checklist: MVP Testing (GOO-135)

**Date**: 2026-01-14
**Branch**: `004-research-assistant-feature`
**Commit**: `385f371`

---

## ✅ Code Review Checklist

### Backend Verification

- [x] **Migrations Created**
  - ✅ d9f3g4h5i6j7_extend_citations_metadata.py
  - ✅ e0g4h5i6j7k8_create_citation_relationships.py
  - ✅ f1h5i6j7k8l9_extend_collections_research.py
  - ✅ g2i6j7k8l9m0_create_project_notes.py
  - ✅ h3j7k8l9m0n1_create_generated_drafts.py

- [x] **API Routes Registered**
  - ✅ Citations router imported in `main.py:62`
  - ✅ Router registered in `main.py:310`

- [x] **Services Created**
  - ✅ `message_citation_service.py` - Citation extraction
  - ✅ `citation_extraction_service.py` - Hybrid extraction
  - ✅ `bibliography_service.py` - Format exports

- [x] **Models Updated**
  - ✅ `citation.py` - Extended with metadata fields
  - ✅ `citation_relationship.py` - Graph edges
  - ✅ `generated_draft.py` - Draft versions
  - ✅ `project_note.py` - Project notes

- [x] **Observability**
  - ✅ Structured logging in message_citation_service.py
  - ✅ Timing metrics (duration_ms)
  - ✅ Event tracking (citation_created, citation_batch_created)

### Frontend Verification

- [x] **Citation Components**
  - ✅ `CitationPreview.tsx` - Popover component
  - ✅ `CitationLink.tsx` - Already exists (reusable)

- [x] **Services Updated**
  - ✅ `ragService.ts` - Added parseCitationIndices(), persistCitations()
  - ✅ `citationService.ts` - API client created
  - ✅ `citationStore.ts` - Zustand store created

- [x] **Chat Integration**
  - ✅ `chat/page.tsx` - Calls ragService.persistCitations()
  - ✅ Citation persistence after message save

- [x] **Type Definitions**
  - ✅ `research.ts` - Citation types, Project types, Draft types

---

## 🔧 Environment Setup

### 1. Check Docker Services

```bash
# Verify all services are running
docker ps | grep -E "postgres|neo4j|qdrant|redis"

# Expected output:
# rag-postgres-1    Up 2 hours   0.0.0.0:5432->5432/tcp
# rag-neo4j-1       Up 2 hours   7474/tcp, 0.0.0.0:7687->7687/tcp
# rag-qdrant-1      Up 2 hours   0.0.0.0:6333->6333/tcp
# rag-redis-1       Up 2 hours   0.0.0.0:6379->6379/tcp
```

**Status**: [ ] Pass / [ ] Fail

---

### 2. Run Database Migrations

```bash
cd backend

# Check current migration status
alembic current

# Run migrations
alembic upgrade head

# Verify migrations applied
alembic current
# Expected: h3j7k8l9m0n1 (head)
```

**Status**: [ ] Pass / [ ] Fail

---

### 3. Verify Database Schema

```bash
# Connect to PostgreSQL
docker exec -it rag-postgres-1 psql -U postgres -d multimodal_rag_dev

# Check citations table
\d citations

# Expected columns:
# - id, message_id, document_id, document_title
# - authors, year, venue, doi, arxiv_id, abstract
# - snippet, page_number, score
# - metadata_source, needs_review
# - created_at, updated_at
```

**Status**: [ ] Pass / [ ] Fail

---

### 4. Check Backend Dependencies

```bash
cd backend

# Verify pybtex installed
pip list | grep pybtex
# Expected: pybtex==0.24.0

# Verify aiohttp-retry installed
pip list | grep aiohttp-retry
# Expected: aiohttp-retry==2.8.3
```

**Status**: [ ] Pass / [ ] Fail

---

### 5. Verify Backend Starts

```bash
cd backend

# Start backend
uvicorn src.main:app --reload --port 8000

# Check logs for:
# ✅ "Application startup complete"
# ✅ "Citations router registered"
# ❌ No import errors
# ❌ No database connection errors
```

**Status**: [ ] Pass / [ ] Fail

---

### 6. Test API Endpoints

```bash
# Test citations endpoint
curl http://localhost:8000/api/v1/citations

# Expected: 200 OK with empty list or existing citations

# Test OpenAPI docs
curl http://localhost:8000/docs

# Expected: 200 OK, Swagger UI loads
```

**Status**: [ ] Pass / [ ] Fail

---

### 7. Check Frontend Dependencies

```bash
cd frontend

# Verify cytoscape packages
npm list | grep cytoscape
# Expected:
# ├─ cytoscape@3.28.1
# ├─ cytoscape-popper@2.0.0
# ├─ cytoscape-context-menus@4.1.0
```

**Status**: [ ] Pass / [ ] Fail

---

### 8. Verify Frontend Builds

```bash
cd frontend

# Build frontend
npm run build

# Expected:
# ✓ Compiled successfully
# No TypeScript errors
# No module not found errors
```

**Status**: [ ] Pass / [ ] Fail

---

### 9. Start Frontend Dev Server

```bash
cd frontend

# Start dev server
npm run dev

# Check logs for:
# ✅ "Ready in Xms"
# ✅ "Local: http://localhost:3000"
# ❌ No compilation errors
```

**Status**: [ ] Pass / [ ] Fail

---

### 10. Verify Frontend Access

```bash
# Open browser
open http://localhost:3000

# Verify:
# ✅ Login page loads
# ✅ Can log in with demo credentials
# ✅ Chat page accessible: /chat
# ❌ No console errors
```

**Status**: [ ] Pass / [ ] Fail

---

## 🧪 Quick Smoke Test

### Test 1: API Health Check

```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Citations endpoint
curl http://localhost:8000/api/v1/citations
# Expected: {"citations":[],"total":0} or existing data
```

**Status**: [ ] Pass / [ ] Fail

---

### Test 2: Frontend Loads

1. Navigate to: http://localhost:3000/chat
2. Open browser DevTools (F12)
3. Check Console tab

**Expected**:
- ✅ No red errors
- ✅ API calls succeed (Network tab)
- ✅ Chat interface renders

**Status**: [ ] Pass / [ ] Fail

---

### Test 3: RAG Service Available

Open browser console and run:

```javascript
// Check if RAG service is available
console.log(typeof window);

// Should not see errors for:
// - ragService undefined
// - citationService undefined
// - citationStore undefined
```

**Status**: [ ] Pass / [ ] Fail

---

## 📋 Final Pre-Flight Status

### Critical Blockers (Must Pass)
- [ ] Database migrations applied
- [ ] Backend starts without errors
- [ ] Frontend builds successfully
- [ ] API endpoints accessible
- [ ] Chat page loads

### Non-Critical (Can proceed with caution)
- [ ] Cytoscape packages installed (needed for Phase 2)
- [ ] All Docker services running (can run with PostgreSQL only)

---

## 🚀 Ready for Testing?

**Overall Status**: [ ] READY / [ ] NOT READY

**If NOT READY**:
- List blockers: _______________________
- Estimated fix time: _______________________

**If READY**:
- Proceed to: [TEST_PLAN.md](./TEST_PLAN.md)
- Start with: Scenario 1 (Basic RAG Citation Flow)

---

## 🆘 Common Issues & Fixes

### Issue 1: Migrations Fail

**Error**: `Target database is not up to date`

**Fix**:
```bash
# Reset migrations (development only!)
alembic downgrade base
alembic upgrade head
```

---

### Issue 2: Backend Import Errors

**Error**: `ModuleNotFoundError: No module named 'pybtex'`

**Fix**:
```bash
cd backend
pip install -r requirements.txt --force-reinstall
```

---

### Issue 3: Frontend Build Errors

**Error**: `Module not found: Can't resolve '@/components/citations/CitationPreview'`

**Fix**:
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run build
```

---

### Issue 4: Database Connection Failed

**Error**: `could not connect to server: Connection refused`

**Fix**:
```bash
# Restart PostgreSQL
docker-compose -f docker-compose.development.yml restart postgres

# Wait 10 seconds
sleep 10

# Try again
cd backend
uvicorn src.main:app --reload
```

---

### Issue 5: Port Already in Use

**Error**: `Address already in use: 8000`

**Fix**:
```bash
# Find process using port
lsof -ti:8000

# Kill process
kill -9 $(lsof -ti:8000)

# Restart
uvicorn src.main:app --reload --port 8000
```

---

## 📝 Notes

- Take screenshots of any errors
- Copy full error messages for debugging
- Document any deviations from expected behavior
- If stuck for >15 minutes, create Linear ticket

---

**Prepared by**: Claude Sonnet 4.5
**Last Updated**: 2026-01-14
**Next Review**: After MVP testing complete
