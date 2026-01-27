# Database Migration i4k8l9m0n1o2 Applied - Project Chat Integration

**Date**: 2026-01-27  
**Status**: ✓ Applied and Verified  
**Feature**: Research Projects + Chat Integration Phase 1  
**Migration ID**: i4k8l9m0n1o2_add_project_thread_integration

## Migration Overview

Adds project-thread integration to the RAG system database, enabling users to start chat conversations scoped to project documents.

## Database Changes

### New Tables

**project_threads** (Junction table):
```sql
CREATE TABLE project_threads (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  link_type VARCHAR(50) NOT NULL,  -- 'auto', 'manual', 'from_chat'
  linked_at TIMESTAMP NOT NULL,
  linked_by_id UUID NOT NULL REFERENCES users(id),
  context_note TEXT,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMP,
  UNIQUE(project_id, thread_id)
);

CREATE INDEX idx_project_threads_project_id ON project_threads(project_id);
CREATE INDEX idx_project_threads_thread_id ON project_threads(thread_id);
CREATE INDEX idx_project_threads_linked_by ON project_threads(linked_by_id);
```

### Modified Tables

**threads** table additions:
```sql
ALTER TABLE threads ADD COLUMN source_project_id UUID REFERENCES collections(id) ON DELETE SET NULL;
ALTER TABLE threads ADD COLUMN rag_document_scope JSONB;
CREATE INDEX idx_threads_source_project ON threads(source_project_id);
```

## Column Descriptions

### project_threads.link_type
- `auto`: Thread created via POST /api/v1/projects/{id}/chat/start
- `manual`: Thread linked via POST /api/v1/projects/{id}/chat/link
- `from_chat`: Thread created via /api/v2/threads with project_id

### threads.rag_document_scope
JSONB field storing document IDs for RAG filtering:
```json
{
  "document_ids": ["doc-uuid-1", "doc-uuid-2", "doc-uuid-3"]
}
```
Set immutably at thread creation time. Users can manually refresh via API.

### threads.source_project_id
Quick reverse lookup FK. Answers: "Which project started this thread?"
- Optional (threads can exist without projects)
- Points to collections table (projects are stored as collections)
- Cascade delete not used (project deletion doesn't delete thread)

## Related Models

**ProjectThread** (`backend/src/models/project_thread.py`):
```python
class ProjectThread(Base):
    __tablename__ = "project_threads"
    
    id: UUID = Column(UUID, primary_key=True, default=uuid4)
    project_id: UUID = Column(UUID, ForeignKey("collections.id", ondelete="CASCADE"))
    thread_id: UUID = Column(UUID, ForeignKey("threads.id", ondelete="CASCADE"))
    link_type: str = Column(String(50), nullable=False)
    linked_at: datetime = Column(DateTime, nullable=False)
    linked_by_id: UUID = Column(UUID, ForeignKey("users.id"))
    context_note: Optional[str] = Column(Text)
    is_deleted: bool = Column(Boolean, default=False)
    deleted_at: Optional[datetime] = Column(DateTime)
    
    # Relationships
    project: Relationship = relationship("Collection")
    thread: Relationship = relationship("Thread")
    linked_by: Relationship = relationship("User")
```

**ProjectThreadLinkType** enum:
```python
class ProjectThreadLinkType(PyEnum):
    AUTO = "auto"          # From POST /chat/start
    MANUAL = "manual"      # From POST /chat/link
    FROM_CHAT = "from_chat" # From thread creation with project_id
```

## API Layer Integration

### Affected API Endpoints

**Phase 2 (Backend API)** - `/api/v1/projects/{id}/chat/*`:
- POST /chat/start - Create chat with project documents
- POST /chat/link - Link existing thread
- GET /chat/threads - List linked threads
- DELETE /chat/threads/{thread_id} - Unlink thread
- POST /chat/save-to-note - Save to project note

### Data Flow

1. **Create Chat with Project Context**:
   - POST `/api/v1/projects/{project_id}/chat/start`
   - Queries `collections.collection_documents` to get document IDs
   - Creates thread with `rag_document_scope` = {document_ids: []}
   - Creates `project_threads` entry with type=AUTO

2. **Link Existing Thread**:
   - POST `/api/v1/projects/{project_id}/chat/link` with thread_id
   - Validates thread is in same workspace
   - Creates `project_threads` entry with type=MANUAL

3. **Auto-linking on Thread Create**:
   - POST `/api/v2/threads` with optional `project_id`
   - If project_id provided and user has access:
     - Sets `thread.source_project_id`
     - Sets `thread.rag_document_scope`
     - Creates `project_threads` entry with type=FROM_CHAT
   - If auto-linking fails: logs warning, doesn't block thread creation

## Recovery Notes

**Applied**: 2026-01-27  
**Challenge**: Database in inconsistent state (alembic_version out of sync)  
**Solution**: Manual SQL application + alembic stamp

**Recovery Steps if Needed**:
```bash
# Check current state
alembic current

# If showing wrong version, check schema
psql -U postgres -d multimodal_rag_dev -c "\d threads"
psql -U postgres -d multimodal_rag_dev -c "\d project_threads"

# If schema exists but version wrong, stamp it
alembic stamp i4k8l9m0n1o2

# Verify
alembic current
alembic history --verbose
```

## Performance Notes

- **Indexes on lookup columns**: project_id, thread_id, linked_by_id for fast queries
- **Document scope as immutable JSONB**: Avoids expensive joins during RAG retrieval
- **Unique constraint**: Prevents duplicate project-thread links
- **Cascade delete**: Automatic cleanup when projects/threads deleted

## Testing Status

- ✓ SQLAlchemy models created and validated
- ✓ Migration syntax verified
- ✓ Foreign keys and cascade delete tested
- ✓ Applied to development database
- ⏳ Unit tests for API endpoints (Phase 3)
- ⏳ Integration tests for full workflows (Phase 3)

## File References

- **Migration**: `backend/alembic/versions/i4k8l9m0n1o2_add_project_thread_integration.py`
- **Model**: `backend/src/models/project_thread.py`
- **Thread Enhancement**: `backend/src/models/thread.py`
- **API**: `backend/src/api/research/project_chat.py` (Phase 2)
- **Schemas**: `backend/src/shared/research_schemas.py`

## Tags

#database #migration #project-chat-integration #sqlalchemy #rag #phase-1