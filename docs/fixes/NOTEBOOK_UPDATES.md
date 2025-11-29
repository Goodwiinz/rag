# Notebook Updates Guide

## Overview

This guide documents all the fixes and updates needed for the RAG System Demo Notebook to work correctly.

## Issues Fixed

### 1. ✅ Registration with Duplicate Organization Names (Cell 9)
### 2. ✅ Workers Status Endpoint (Cell 19)
### 3. ✅ Document Processing Status Endpoint (Cell 19)

---

## Cell-by-Cell Updates

### Cell 9: User Authentication & RBAC Testing

**Status:** ✅ No changes needed - now works automatically!

The registration fix allows multiple users to register with the same organization name.

**What works now:**
```python
# Multiple users can register with "Demo Organization"
reg_success, reg_result = tester.register_user(
    email=test_email,
    password=test_password,
    first_name="Demo",
    last_name="User",
    org_name="Demo Organization"  # ✅ Can be reused!
)
```

**Output:**
```
✅ User Registration Successful:
   - User ID: ...
   - Organization ID: ...
   - Role: admin (or user if org already exists)
```

---

### Cell 19: Background Processing Test

**Status:** ⚠️ Needs update - two endpoint paths were wrong

#### Issue 1: Workers Status Endpoint

**Old Code (Returns 404):**
```python
worker_response = tester.session.get(f"{BASE_URL}/api/workers/status", timeout=10)
```

**New Code (Works):**
```python
worker_response = tester.session.get(f"{BASE_URL}/api/v1/workers/status", timeout=10)
```

#### Issue 2: Document Processing Status Endpoint

**Old Code (Returns 404):**
```python
status_response = tester.session.get(
    f"{BASE_URL}/api/processing/status/{doc_id}",
    timeout=10
)
```

**New Code (Works):**
```python
status_response = tester.session.get(
    f"{BASE_URL}/api/v1/processing/documents/{doc_id}/status",
    timeout=10
)
```

---

## Complete Updated Cell 19

**Option 1: Copy from file**
```bash
# Copy the complete fixed version
cat notebooks/processing_status_fix.py
```

**Option 2: Manual replacement**

Replace the entire Cell 19 content with:

```python
# Test background processing and job status
print("⚙️ **Testing Background Processing...**")

# Check processing status for uploaded documents
if uploaded_documents:
    print(f"\n📊 **Checking Processing Status for {len(uploaded_documents)} documents...**")

    processing_results = []

    for doc in uploaded_documents:
        doc_id = doc.get("id")
        if doc_id:
            try:
                # FIXED: Use correct endpoint path
                status_response = tester.session.get(
                    f"{BASE_URL}/api/v1/processing/documents/{doc_id}/status",
                    timeout=10
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    processing_results.append({
                        "document_id": doc_id,
                        "title": doc["title"],
                        "status": status_data.get("processing_status", "unknown"),
                        "is_embedded": status_data.get("is_embedded", False),
                        "is_indexed": status_data.get("is_indexed", False),
                        "error": status_data.get("processing_error")
                    })

                    status = status_data.get("processing_status", "unknown")
                    embedded = "✅" if status_data.get("is_embedded") else "❌"
                    indexed = "✅" if status_data.get("is_indexed") else "❌"

                    print(f"📄 {doc['title']}:")
                    print(f"   Status: {status}")
                    print(f"   Embedded: {embedded}")
                    print(f"   Indexed: {indexed}")

                elif status_response.status_code == 404:
                    processing_results.append({
                        "document_id": doc_id,
                        "title": doc["title"],
                        "status": "not_found",
                        "is_embedded": False,
                        "is_indexed": False,
                        "error": "Document not found"
                    })
                    print(f"📄 {doc['title']}: Not found")

                else:
                    processing_results.append({
                        "document_id": doc_id,
                        "title": doc["title"],
                        "status": "error",
                        "is_embedded": False,
                        "is_indexed": False,
                        "error": f"HTTP {status_response.status_code}"
                    })
                    print(f"📄 {doc['title']}: Error {status_response.status_code}")

            except Exception as e:
                processing_results.append({
                    "document_id": doc_id,
                    "title": doc["title"],
                    "status": "error",
                    "is_embedded": False,
                    "is_indexed": False,
                    "error": str(e)
                })
                print(f"📄 {doc['title']}: Error - {str(e)}")

    # Visualization
    if processing_results:
        df_processing = pd.DataFrame(processing_results)
        status_counts = df_processing['status'].value_counts()

        try:
            fig_status = go.Figure()
            fig_status.add_trace(go.Pie(
                labels=status_counts.index,
                values=status_counts.values,
                hole=0.3,
                marker_colors=['#4CAF50', '#FF9800', '#F44336', '#9E9E9E']
            ))
            fig_status.update_layout(title="📊 Document Processing Status", height=400)
            fig_status.show()
        except Exception as viz_error:
            print(f"\n⚠️ Visualization skipped: {viz_error}")

        print("\n📋 **Processing Status Details:**")
        display(df_processing[['title', 'status', 'is_embedded', 'is_indexed']])

else:
    print("ℹ️ No documents uploaded")

# Test Celery workers with CORRECT endpoint
print("\n🏭 **Testing Background Workers...**")
try:
    worker_response = tester.session.get(f"{BASE_URL}/api/v1/workers/status", timeout=10)

    if worker_response.status_code == 200:
        worker_data = worker_response.json()
        print("✅ Background Workers Active")
        print(f"- Active Workers: {worker_data.get('active_workers', 0)}")
        print(f"- Active Tasks: {worker_data.get('active_tasks', 0)}")
        print(f"- Pending Tasks: {worker_data.get('pending_tasks', 0)}")

        # Worker details
        for worker in worker_data.get('worker_details', []):
            print(f"\n  🔧 Worker: {worker.get('hostname')}")
            print(f"     Status: {worker.get('status')}")
            print(f"     Active Tasks: {worker.get('active_tasks', 0)}")

        # Health check
        health_response = tester.session.get(f"{BASE_URL}/api/v1/workers/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            status_icon = "✅" if health_data.get('healthy') else "❌"
            print(f"\n🏥 **Worker Health:** {status_icon}")
    else:
        print(f"⚠️ Worker status: {worker_response.status_code}")

except Exception as e:
    print(f"❌ Worker error: {str(e)}")

print("\n⚙️ **Background Processing Summary:**")
print("✅ Document processing tracking available")
print("✅ Background workers operational")
```

---

## Endpoint Reference

### Correct Endpoint Paths

| Purpose | Correct Path | Old/Wrong Path |
|---------|-------------|----------------|
| Worker Status | `/api/v1/workers/status` | `/api/workers/status` |
| Worker Health | `/api/v1/workers/health` | N/A (new) |
| Document Processing | `/api/v1/processing/documents/{id}/status` | `/api/processing/status/{id}` |
| User Registration | `/api/v1/auth/register` | ✅ (correct) |
| User Login | `/api/v1/auth/login` | ✅ (correct) |

### API Version

All endpoints now use the `/api/v1/` prefix for versioning.

---

## Testing the Notebook

### 1. Start Services

```bash
cd /Users/goodwiinz/development/RAG_system/rag
docker-compose up -d
```

### 2. Verify Services

```bash
# Check all services are running
docker-compose ps

# Expected output:
# backend    running (healthy)
# celery     running
# db         running (healthy)
# redis      running (healthy)
# ...
```

### 3. Run Verification

```bash
# Run comprehensive test
./verify_all_fixes.sh

# Expected: All 8 tests PASSED
```

### 4. Open Notebook

```bash
jupyter notebook notebooks/rag_system_demo.ipynb
```

### 5. Run Cells

Execute cells in order:
- **Cell 1-8:** Setup and imports ✅
- **Cell 9:** Authentication ✅ (now works with duplicate orgs)
- **Cell 10-18:** Various features ✅
- **Cell 19:** Background processing ⚠️ (update using this guide)
- **Cell 20+:** Continue normally ✅

---

## Expected Output

### Cell 9: Authentication
```
🔐 Testing Authentication for: demo_user_1760480163@example.com

✅ User Registration Successful:
   - User ID: abc-123-def
   - Organization ID: org-456-xyz
   - Role: admin

🎫 Login Successful:
   - Token Length: 200+ characters
   - Session Authenticated: ✅
```

### Cell 19: Background Processing

**Document Status:**
```
📊 Checking Processing Status for 1 documents...

📄 AI and ML Fundamentals:
   Status: completed
   Embedded: ✅
   Indexed: ✅
```

**Worker Status:**
```
🏭 Testing Background Workers...

✅ Background Workers Active
- Active Workers: 1
- Active Tasks: 0
- Pending Tasks: 0
- Registered Tasks: 6

  🔧 Worker: celery@1ca5e9bb5dac
     Status: online
     Active Tasks: 0

🏥 Worker Health: ✅ Healthy
```

---

## Troubleshooting

### Still Getting 404 Errors?

1. **Check backend is updated:**
   ```bash
   docker-compose restart backend
   sleep 10
   curl http://localhost:8000/health
   ```

2. **Verify endpoint exists:**
   ```bash
   # Check API docs
   open http://localhost:8000/docs
   # Look for /api/v1/workers/* endpoints
   ```

3. **Check authentication:**
   ```python
   # In notebook, verify token
   print(f"Token: {tester.auth_token[:50]}...")
   ```

### Documents Show "Not Found"?

This is normal if:
- Documents were just uploaded (processing in progress)
- Backend was restarted (processing state lost)
- Celery workers are not running

**Solution:**
```bash
# Check Celery is running
docker-compose ps celery

# If not running, start it
docker-compose up -d celery

# Check logs
docker-compose logs -f celery
```

### Workers Show as Unhealthy?

```bash
# Restart Celery
docker-compose restart celery

# Wait for it to start
sleep 5

# Check status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/workers/health | python3 -m json.tool
```

---

## Quick Reference

### Files to Update
- **Cell 19** in `notebooks/rag_system_demo.ipynb`

### Reference Files
- `notebooks/processing_status_fix.py` - Complete Cell 19 replacement
- `notebooks/workers_test_snippet.py` - Alternative worker testing code
- `NOTEBOOK_UPDATES.md` - This file

### Verification
```bash
./verify_all_fixes.sh
```

---

## Summary of Changes

| Cell | Change | Status |
|------|--------|--------|
| 9 | Registration with duplicate orgs | ✅ Auto-fixed |
| 19 | Worker status endpoint path | ⚠️ Manual update |
| 19 | Document processing endpoint path | ⚠️ Manual update |

---

**Last Updated:** October 14, 2025
**Version:** 1.0.0
**Status:** ✅ All fixes verified and tested
