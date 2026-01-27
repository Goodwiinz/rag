# Draft Generation API Design (T079-T086)

## Architecture Decision: Async with Polling

The literature review draft generation uses asynchronous processing with polling:

1. **Submission Phase** (POST /drafts)
   - Returns 202 Accepted with task_id
   - DraftGenerationService.generate_draft() starts async job
   - Does NOT wait for completion

2. **Status Polling** (GET /status/{task_id})
   - Client polls periodically
   - DraftGenerationService.get_status(task_id) returns current state
   - Supports cancellation via POST /cancel/{task_id}

3. **Retrieval Phase** (GET /current or /{draft_id})
   - Fetch completed draft
   - Includes all metadata: word_count, citation_count, themes, generation_params

## Security Pattern: Authorization Validation

All endpoints use `_validate_project_ownership()` helper:
- Joins Collection with Workspace
- Checks Workspace.owner_id == current_user.id
- Returns 404 for both "not found" and "not authorized" (prevents info leakage)

## API Response Format

Draft response includes:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "version": 1,
  "title": "Generated Title",
  "content": "Full markdown content",
  "themes": ["theme1", "theme2"],
  "word_count": 5000,
  "citation_count": 25,
  "generation_params": {...},
  "is_current": true,
  "created_at": "2026-01-27T..."
}
```

## Affected Files
- `backend/src/api/research/drafts.py` - Main API implementation
- `backend/src/services/research/draft_generation_service.py` - Business logic (linked)
- `backend/src/shared/research_schemas.py` - Request/response schemas (linked)

## Key Query Parameters
- `themes`: Required list of themes to focus on
- `style`: academic|technical|summary (default: academic)
- `max_sections`: 2-10 (default: 5)
- `include_abstract`: bool (default: true)
- `document_ids`: Optional list to limit documents included

## Status Codes Used
- 202 Accepted: Draft generation started successfully
- 404 Not Found: Project not found or access denied
- 400 Bad Request: Invalid parameters or cancellation failed
- 500 Internal Server Error: Processing or generation error

## Test Coverage Area
DocumentFactory can generate:
- Test documents for draft inclusion
- Processing jobs that simulate background work
- Quality assessments for cited documents

Tags: #api #research #async #architecture #security
