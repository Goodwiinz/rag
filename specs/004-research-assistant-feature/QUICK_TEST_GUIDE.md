# Quick Test Guide: 5-Minute MVP Validation

**Goal**: Verify GOO-135 works end-to-end in under 5 minutes

---

## ⚡ Quick Start (First Time)

```bash
# 1. Start services (if not running)
docker-compose -f docker-compose.development.yml up -d postgres

# 2. Run migrations
cd backend && alembic upgrade head

# 3. Start backend
uvicorn src.main:app --reload --port 8000 &

# 4. Start frontend
cd ../frontend && npm run dev &

# 5. Wait 30 seconds for both to start
sleep 30
```

---

## 🎯 5-Minute Test Flow

### Step 1: Login (30 seconds)

1. Open: http://localhost:3000
2. Login with demo account:
   - Email: `demo@multimodal-rag.com`
   - Password: `demo123`
3. Navigate to Chat: http://localhost:3000/chat

---

### Step 2: Upload Test Document (60 seconds)

**Option A: Use Existing Document**
- If you have documents already uploaded, skip to Step 3

**Option B: Quick Upload**
1. Click "Upload Document" button
2. Select any PDF (research paper recommended)
3. Wait for processing to complete
4. Status should change: Queued → Processing → Indexed

**Option C: Use Sample ArXiv Paper**
```bash
# Download sample paper
curl -o /tmp/sample-paper.pdf https://arxiv.org/pdf/2301.00234.pdf

# Upload via UI or API
```

---

### Step 3: Enable RAG & Select Model (30 seconds)

1. Find RAG toggle switch (near model selector)
2. Toggle ON (should turn green/phosphor)
3. Select WebLLM model:
   - **Recommended**: Llama-3.2-1B (fastest, 4GB RAM)
   - Alternative: Phi-3.5-mini (more accurate, 8GB RAM)

**First-time note**: Model download may take 2-5 minutes (cached after first use)

---

### Step 4: Ask Test Question (60 seconds)

Type one of these questions:

**For ML/AI papers**:
```
What are the main contributions of this paper?
```

**For research papers**:
```
Summarize the methodology described in this document.
```

**Generic**:
```
What are the key findings?
```

**Wait for response** (30-90 seconds for first inference)

---

### Step 5: Verify Citations (30 seconds)

**Check 1: Citations in Response**
- [ ] Response contains `[Doc 1]` references
- [ ] Citations styled as clickable links (different color)

**Check 2: Citation Popover**
- [ ] Click `[Doc 1]`
- [ ] Popover appears with:
  - Document title
  - Relevance score (e.g., "85%")
  - Text snippet

**Check 3: Console Logs**
- [ ] Open browser DevTools (F12)
- [ ] Check Console tab
- [ ] Look for: `[RAG] Persisted N citations`

---

### Step 6: Verify Persistence (30 seconds)

1. Refresh browser (Cmd+R / Ctrl+R)
2. Navigate back to chat
3. Scroll to message with citations

**Expected**:
- [ ] Citations still appear
- [ ] Popover still works
- [ ] No errors in console

---

## ✅ Success Criteria

**Test PASSES if**:
- ✅ Response includes `[Doc N]` citations
- ✅ Citations are clickable
- ✅ Popover shows document info
- ✅ Console shows "Persisted N citations"
- ✅ Citations persist after refresh

**Test FAILS if**:
- ❌ No citations in response
- ❌ Citations not clickable
- ❌ Popover doesn't appear
- ❌ Errors in console
- ❌ Citations disappear after refresh

---

## 🐛 Common Issues

### Issue 1: No Citations in Response

**Possible Causes**:
- RAG toggle is OFF
- No documents indexed
- Model doesn't follow citation format

**Fix**:
1. Verify RAG toggle is ON (green)
2. Check document status is "indexed"
3. Try different question
4. Check backend logs for retrieval

---

### Issue 2: Citations Not Clickable

**Possible Causes**:
- Frontend citation rendering issue
- CitationLink component not integrated

**Fix**:
1. Check browser console for errors
2. Verify `CitationLink` component imported
3. Check `ChatMessage.tsx` uses `CitationRenderer`

---

### Issue 3: Popover Doesn't Appear

**Possible Causes**:
- Styling conflict
- Popover component not imported
- Citation data missing

**Fix**:
1. Check DevTools Elements tab for popover HTML
2. Verify shadcn Popover installed
3. Check citation store has data

---

### Issue 4: "Persisted N citations" Not in Console

**Possible Causes**:
- Citation service not called
- API error (check Network tab)
- Database connection issue

**Fix**:
1. Check Network tab for `/api/v1/citations` POST
2. Look for error responses
3. Check backend terminal for errors
4. Verify database migrations applied

---

### Issue 5: Model Download Timeout

**Error**: WebLLM shows "Downloading model... timeout"

**Fix**:
1. Check internet connection
2. Wait longer (large models take 5+ minutes)
3. Try smaller model (Llama-3.2-1B)
4. Check browser console for specific error

---

## 🔍 Debug Commands

### Check Citations in Database

```bash
docker exec -it rag-postgres-1 psql -U postgres -d multimodal_rag_dev -c "
SELECT
    c.document_title,
    c.score,
    c.metadata_source,
    c.created_at
FROM citations c
ORDER BY c.created_at DESC
LIMIT 5;"
```

---

### Check Backend Logs

```bash
# Filter for citation-related logs
docker-compose -f docker-compose.development.yml logs backend | grep -i citation

# Look for:
# - "citations_saved"
# - "citation_created"
# - Any ERROR messages
```

---

### Check Frontend Network Requests

1. Open DevTools (F12)
2. Go to Network tab
3. Filter by "citations"
4. Look for POST requests
5. Check response status (should be 201)

---

## 📊 What to Report

If test **FAILS**, collect this info:

1. **Browser**: Chrome/Firefox/Edge version
2. **Error Messages**: From console and Network tab
3. **Backend Logs**: Last 50 lines with "citation"
4. **Screenshot**: Of the issue
5. **Steps**: Exact steps you took
6. **Database**: Run debug command above

---

## 🎉 Test Complete!

**If test PASSED**:
- ✅ Move GOO-135 to "Done" in Linear
- ✅ Continue to full test plan: [TEST_PLAN.md](./TEST_PLAN.md)
- ✅ Or proceed to GOO-136 frontend implementation

**If test FAILED**:
- 📝 Create bug ticket in Linear
- 📋 Attach debug info
- 🔧 Tag as "testing-blocker"
- 🆘 Get help from team

---

**Testing Time**: ~5 minutes (excluding first-time model download)
**Model Download**: 2-5 minutes (one-time, cached)
**Total First Run**: ~10 minutes
**Subsequent Runs**: ~5 minutes
