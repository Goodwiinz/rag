# Phase 1: Research Projects + Chat Integration - Database & Models Completed

**Date**: 2026-01-27  
**Status**: ✓ Complete (Database & Models)  
**Next Phase**: Phase 2 - Backend API Implementation

## Summary

Phase 1 of the Research Projects + Chat Integration project successfully completed. All database schema changes and SQLAlchemy models have been implemented and validated. The migration file is ready for deployment but has not yet been applied to the development database.

## Files Created

### 1. ProjectThread Model
**File**: `backend/src/models/project_thread.py`

```python
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import BaseModel
from .types import GUID

class ProjectThreadLinkType(PyEnum):
    AUTO = "auto"
    MANUAL = "manual"
    FROM_CHAT = "from_chat"

class ProjectThread(BaseModel):
    __tablename__ = "project_threads"
    
    project_id = Column(GUID(), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(GUID(), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String(50), default=ProjectThreadLinkType.MANUAL.value, nullable=False)
    linked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    linked_by_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    context_note = Column(Text, nullable=True)
    
    # Relationships
    project = relationship("Collection")
    thread = relationship("Thread")
    linked_by = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("project_id", "thread_id", name="uq_project_thread"),
    )
```

**Key Features**:
- ProjectThreadLinkType enum with AUTO, MANUAL, FROM_CHAT values
- Foreign key relationships with cascade delete for collections and threads
- Unique constraint to prevent duplicate links
- Tracks who linked the thread and when
- Optional context_note for user annotations

### 2. Alembic Migration
**File**: `backend/alembic/versions/i4k8l9m0n1o2_add_project_thread_integration.py`

Creates the `project_threads` junction table with:
- UUID primary key
- Foreign keys to `collections` and `threads` with CASCADE DELETE
- Foreign key to `users` for audit tracking
- Unique constraint on (project_id, thread_id)
- Indexes on project_id and thread_id for fast lookups

Also adds optional columns to `threads` table:
- `source_project_id`: UUID reference to the project that initiated the chat
- `rag_document_scope`: JSONB field storing document IDs as `{"document_ids": ["uuid1", "uuid2"]}`

## Files Modified

### 1. Thread Model Enhancement
**File**: `backend/src/models/thread.py`

Added columns for project integration:
```python
# Optional reference to the project that started this thread
source_project_id = Column(GUID(), ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)

# JSONB field storing document IDs when thread is scoped to project documents
# Format: {"document_ids": ["uuid1", "uuid2", ...]}
rag_document_scope = Column(JSONB, nullable=True)
```

**Rationale**:
- `source_project_id`: Enables quick lookup of which project initiated a chat (no join needed)
- `rag_document_scope`: Stores document filtering context for RAG retrieval, set at thread creation time for performance

### 2. Model Exports
**File**: `backend/src/models/__init__.py`

Added exports:
```python
from .project_thread import ProjectThread, ProjectThreadLinkType

__all__ = [
    "ProjectThread",
    "ProjectThreadLinkType",
    # ... existing exports
]
```

## Database Schema

### project_threads Table
```sql
CREATE TABLE project_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL DEFAULT 'manual',
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    linked_by_id UUID REFERENCES users(id),
    context_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, thread_id)
);

CREATE INDEX idx_project_threads_project_id ON project_threads(project_id);
CREATE INDEX idx_project_threads_thread_id ON project_threads(thread_id);
```

### threads Table Additions
```sql
ALTER TABLE threads ADD COLUMN source_project_id UUID REFERENCES collections(id) ON DELETE SET NULL;
ALTER TABLE threads ADD COLUMN rag_document_scope JSONB DEFAULT NULL;
```

## Key Architectural Decisions

### 1. Junction Table Pattern
Used many-to-many junction table `project_threads` instead of foreign key on one side. This provides:
- Flexibility for future multi-project linking per thread
- Metadata storage (link_type, linked_by, linked_at)
- Proper cascade behavior on deletion
- Clean separation of concerns

### 2. Cascade Delete Behavior
- When project (collection) is deleted → linked project_threads are cascade deleted
- When thread is deleted → linked project_threads are cascade deleted
- When linked_by user is deleted → project_threads remain (linked_by_id becomes NULL)

### 3. Optional Thread Columns
Made `source_project_id` and `rag_document_scope` optional to:
- Maintain backward compatibility with existing threads
- Allow threads to exist without project context
- Enable gradual migration/adoption

### 4. JSONB for Document Scope
Chose JSONB over separate table for `rag_document_scope` because:
- Immutable at thread creation time (documents shouldn't be added/removed after)
- Single atomic value improves query performance
- Alternative: Users can click "Refresh Context" to update
- Format: `{"document_ids": ["uuid1", "uuid2"]}`

### 5. Link Type Enumeration
Tracks how link was created:
- `MANUAL`: User explicitly linked via UI
- `AUTO`: System-suggested link (future feature)
- `FROM_CHAT`: Thread created directly from project "Start Chat"

## Migration Readiness

### Validation Checklist
- [x] Migration syntax validated
- [x] SQLAlchemy model structure correct
- [x] Foreign key relationships proper
- [x] Unique constraint prevents duplicates
- [x] Cascade delete logic appropriate
- [x] Indexes on lookup columns present
- [x] Enum values match frontend expectations

### Pre-Migration Steps
1. Backup PostgreSQL development database
2. Ensure all existing code is compatible (no direct project_threads references yet)
3. Run migration with: `alembic upgrade head`

### Post-Migration Steps
1. Verify indexes are created: `\d project_threads` in psql
2. Verify constraints: `\d project_threads` shows UNIQUE and FK constraints
3. Update dependent code (Phase 2 - Backend API)
4. No data migration needed (new table, no data transformation)

## Current Status

### ✓ Completed in Phase 1
1. ProjectThread model with all relationships
2. ProjectThreadLinkType enum
3. Alembic migration file with complete DDL
4. Thread model enhancements (source_project_id, rag_document_scope)
5. Model exports updated

### ⏸️ Pending (Phase 2 - Backend API)
1. `/api/v1/projects/{id}/chat/*` router implementation
2. Schemas for request/response validation
3. Service layer for project-chat operations
4. Thread creation flow with project_id parameter
5. Unit and integration tests

### ⏸️ Pending (Phase 3+)
1. Frontend services and components
2. UI integration in project detail page
3. Chat interface enhancements for project context
4. RAG filtering by rag_document_scope

## Related Documentation

- **Plan**: `project_chat_integration_plan` memory
- **Database Schema**: `database_fixes_and_indexing` memory
- **Architecture**: Project CLAUDE.md and docs/architecture/

## Testing Strategy (Phase 2)

### Unit Tests to Add
```python
# backend/tests/test_project_thread_model.py
def test_project_thread_creation()
def test_project_thread_unique_constraint()
def test_project_thread_cascade_delete_on_project()
def test_project_thread_cascade_delete_on_thread()
def test_thread_source_project_optional()
def test_rag_document_scope_jsonb_format()
```

### Integration Tests to Add
```python
# backend/tests/test_project_chat_api.py
def test_start_chat_from_project()
def test_link_existing_thread()
def test_list_project_threads()
def test_unlink_thread()
def test_workspace_boundary_enforcement()
```

## Files Summary

| File | Type | Status | Purpose |
|------|------|--------|---------|
| `backend/src/models/project_thread.py` | CREATE | ✓ Complete | ProjectThread model and enum |
| `backend/alembic/versions/i4k8l9m0n1o2_add_project_thread_integration.py` | CREATE | ✓ Complete | Database migration |
| `backend/src/models/thread.py` | MODIFY | ✓ Complete | Added source_project_id, rag_document_scope |
| `backend/src/models/__init__.py` | MODIFY | ✓ Complete | Export ProjectThread, ProjectThreadLinkType |

## Next Phase Deliverables

Phase 2 will implement the backend API layer:
1. `/api/v1/projects/{id}/chat/start` - Start new chat with project context
2. `/api/v1/projects/{id}/chat/link` - Link existing thread
3. `/api/v1/projects/{id}/chat/threads` - List linked threads
4. `/api/v1/projects/{id}/chat/threads/{id}` - Unlink thread

Complete schemas, service layer, error handling, and validation will be included.

## Related Symbols

The following codebase symbols are involved in this integration:

**Models**:
- `/Collection` - Project model
- `/Thread` - Chat thread model
- `/User` - User/audit tracking
- `/ProjectThread` (new)

**Relationships**:
- Collection → ProjectThread → Thread (many-to-many)
- Thread → Collection (via source_project_id)

**Future APIs**:
- `/api/v1/projects/{id}/chat/*` router
- `/api/v2/threads` enhancements

---

## Tags

#project-chat-integration #database #sqlalchemy #alembic #phase-1 #architecture #completed
