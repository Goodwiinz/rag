# Project-Chat Integration (Condensed)

## Status: Phase 1-4 completed (2026-01-27), known bugs remain

## What Was Built
- ProjectThread junction table (many-to-many: collections ↔ threads)
- Thread enhancements: source_project_id, rag_document_scope (JSONB)
- 5 API endpoints at /api/v1/projects/{id}/chat/*
  - POST /start — create chat with project docs as RAG context
  - POST /link — link existing thread
  - GET /threads — list linked threads
  - DELETE /threads/{id} — unlink
  - POST /save-to-note — export thread to project note
- Frontend: ProjectChatTab, ThreadCard, StartChatModal, SaveToNoteModal

## Known Bugs (as of 2026-01-27)
1. **ProjectThread not persisted** — API returns 200 but transaction rolls back. Thread + conversation created, but project_threads link missing. Likely db.refresh() or middleware issue.
2. **Save to Note returns 404** — endpoint may not be registered in router

## Key Files
- backend/src/models/project_thread.py
- backend/src/api/research/project_chat.py (692 lines)
- backend/src/shared/research_schemas.py (6 new schemas)
- Migration: i4k8l9m0n1o2_add_project_thread_integration
