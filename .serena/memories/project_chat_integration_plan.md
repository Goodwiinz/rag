# Research Projects + Chat Integration Plan

## Overview

Integration plan to connect Research Projects (`Collection` model) and Chat systems (`Thread`/`Conversation` models) to enable:
1. Start a chat from a project with project documents as RAG context
2. Link existing threads to projects
3. Save chat insights to project notes
4. View project-related threads in project detail page

## Current Architecture Gap

**Projects System** (`/api/v1/projects`)
- Collection → CollectionDocument → Document
- ProjectNote (markdown notes)
- GeneratedDraft (AI-generated drafts)
- Bibliography generation

**Chat System** (`/api/v2/threads`)
- Workspace → Conversation → Thread → ChatMessage → Citation
- Thread-centric with RAG integration
- Bulk operations support
- Real-time WebSocket updates

**Gap**: NO direct database relationship between `Collection` and `Thread`/`Conversation`. Both exist under `Workspace` but cannot reference each other.

---

## Database Schema Changes

### New Table: `project_threads`

```sql
CREATE TABLE project_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL DEFAULT 'manual',  -- 'auto', 'manual', 'from_chat'
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

### Thread Table Additions (Optional)

```sql
ALTER TABLE threads ADD COLUMN source_project_id UUID REFERENCES collections(id) ON DELETE SET NULL;
ALTER TABLE threads ADD COLUMN rag_document_scope JSONB DEFAULT NULL;
```

**Purpose**:
- `source_project_id`: Quick lookup for "which project started this thread"
- `rag_document_scope`: Store document IDs for RAG filtering `{"document_ids": ["uuid1", "uuid2"]}`

---

## Implementation Phases

### Phase 1: Database & Model (Backend Foundation)

**Files to Create**:
1. `backend/src/models/project_thread.py` - ProjectThread model
2. `backend/alembic/versions/XXXX_add_project_thread_table.py` - Migration

**Files to Modify**:
1. `backend/src/models/__init__.py` - Export ProjectThread
2. `backend/src/models/thread.py` - Add optional fields (source_project_id, rag_document_scope)

**ProjectThread Model**:
```python
class ProjectThreadLinkType(PyEnum):
    AUTO = "auto"
    MANUAL = "manual"
    FROM_CHAT = "from_chat"

class ProjectThread(BaseModel):
    __tablename__ = "project_threads"
    
    project_id = Column(GUID(), ForeignKey("collections.id", ondelete="CASCADE"))
    thread_id = Column(GUID(), ForeignKey("threads.id", ondelete="CASCADE"))
    link_type = Column(Enum(ProjectThreadLinkType))
    linked_at = Column(DateTime(timezone=True))
    linked_by_id = Column(GUID(), ForeignKey("users.id"))
    context_note = Column(Text)
    
    # Relationships
    project = relationship("Collection")
    thread = relationship("Thread")
    linked_by = relationship("User")
```

### Phase 2: Backend API

**Files to Create**:
1. `backend/src/api/research/project_chat.py` - Integration endpoints
2. `backend/src/shared/research_schemas.py` - Add new schemas

**New API Router**: `/api/v1/projects/{id}/chat`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/projects/{id}/chat/start` | POST | Start chat with project docs as RAG context |
| `/projects/{id}/chat/link` | POST | Link existing thread to project |
| `/projects/{id}/chat/threads` | GET | List linked threads |
| `/projects/{id}/chat/threads/{thread_id}` | DELETE | Unlink thread |
| `/projects/{id}/chat/save-to-note` | POST | Save thread to project note |

**Request/Response Schemas**:
```python
class StartChatFromProjectRequest(BaseModel):
    initial_message: str
    conversation_id: Optional[UUID] = None  # Use existing or create new
    thread_title: Optional[str] = None

class StartChatFromProjectResponse(BaseModel):
    thread_id: UUID
    conversation_id: UUID
    project_thread_id: UUID
    document_scope: List[UUID]  # Documents included in RAG

class LinkThreadRequest(BaseModel):
    thread_id: UUID
    context_note: Optional[str] = None

class ProjectThreadResponse(BaseModel):
    id: UUID
    project_id: UUID
    thread_id: UUID
    thread_title: str
    conversation_id: UUID
    link_type: str
    linked_at: datetime
    message_count: int
    last_message_at: datetime

class SaveThreadToNoteRequest(BaseModel):
    thread_id: UUID
    note_title: str
    include_citations: bool = True
```

**Files to Modify**:
1. `backend/src/api/threads/threads.py`:
   - Add optional `project_id` to `ThreadCreate` schema
   - When thread created with `project_id`, auto-create `ProjectThread` link
2. `backend/src/main.py`:
   - Register `project_chat_router`

### Phase 3: Frontend Service & Store

**Files to Create**:
1. `frontend/src/services/projectChatService.ts` - API client
2. `frontend/src/types/project-chat.ts` - TypeScript types

**projectChatService.ts**:
```typescript
export const projectChatService = {
  async startChatFromProject(
    projectId: string,
    request: StartChatFromProjectRequest
  ): Promise<StartChatFromProjectResponse> {
    return apiClient.post(
      `/projects/${projectId}/chat/start`,
      request
    );
  },

  async linkThreadToProject(
    projectId: string,
    request: LinkThreadRequest
  ): Promise<ProjectThreadResponse> {
    return apiClient.post(
      `/projects/${projectId}/chat/link`,
      request
    );
  },

  async listProjectThreads(
    projectId: string
  ): Promise<ProjectThreadResponse[]> {
    return apiClient.get(`/projects/${projectId}/chat/threads`);
  },

  async unlinkThread(
    projectId: string,
    threadId: string
  ): Promise<void> {
    return apiClient.delete(
      `/projects/${projectId}/chat/threads/${threadId}`
    );
  },

  async saveThreadToNote(
    projectId: string,
    request: SaveThreadToNoteRequest
  ): Promise<{ note_id: string }> {
    return apiClient.post(
      `/projects/${projectId}/chat/save-to-note`,
      request
    );
  },
};
```

**Files to Modify**:
1. `frontend/src/store/projectStore.ts`:
   - Add `linkedThreads` state
   - Add actions: `fetchLinkedThreads()`, `startChatFromProject()`, `linkThread()`, `unlinkThread()`

### Phase 4: Frontend UI

**Files to Create**:
1. `frontend/src/components/research/ProjectChatTab.tsx` - Conversations tab

**ProjectChatTab Component**:
```tsx
export function ProjectChatTab({ projectId }: { projectId: string }) {
  const [linkedThreads, setLinkedThreads] = useState<ProjectThreadResponse[]>([]);
  const [isStartingChat, setIsStartingChat] = useState(false);
  
  return (
    <div className="space-y-4">
      {/* Header with action buttons */}
      <div className="flex gap-2">
        <Button onClick={handleNewChat}>
          <MessageSquarePlus className="w-4 h-4 mr-2" />
          New Chat
        </Button>
        <Button variant="outline" onClick={handleLinkExisting}>
          <Link className="w-4 h-4 mr-2" />
          Link Existing Thread
        </Button>
      </div>

      {/* Linked threads list */}
      <div className="space-y-2">
        {linkedThreads.map(thread => (
          <Card key={thread.id}>
            <CardHeader>
              <CardTitle>{thread.thread_title}</CardTitle>
              <CardDescription>
                {thread.message_count} messages • 
                Last active {formatDate(thread.last_message_at)}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Button 
                  onClick={() => navigate(`/chat?thread=${thread.thread_id}`)}
                >
                  Open Chat
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => handleUnlink(thread.thread_id)}
                >
                  Unlink
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

**Files to Modify**:
1. `frontend/app/(dashboard)/projects/[id]/page.tsx`:
   - Add "Conversations" tab (5th tab after Documents, Notes, Bibliography, Drafts)
   - Import and render `ProjectChatTab`

2. `frontend/app/(dashboard)/chat/page.tsx`:
   - Show project context indicator when thread has `source_project_id`
   - Display: `[Project Context: {project_name} | {doc_count} documents]`

### Phase 5: RAG Integration

**Files to Modify**:
1. `backend/src/api/chat.py` (or wherever chat completions are handled):
   - Check if thread has `rag_document_scope`
   - Pass document filter to RAG retrieval service
   - Example: `retrieval_service.retrieve(query, document_ids=thread.rag_document_scope["document_ids"])`

2. `frontend/src/components/chat/ChatInterface.tsx`:
   - Display scoped context indicator
   - Show which documents are in scope for RAG

---

## Key Constraints & Validation

1. **Workspace Boundary**: Thread and project MUST be in same workspace
2. **Unique Links**: `UNIQUE(project_id, thread_id)` prevents duplicates
3. **Cascade Delete**: When project deleted, links deleted automatically
4. **Authorization**: All operations check workspace ownership via existing `_get_project_with_auth()`
5. **Backward Compatible**: Existing threads/projects work unchanged

---

## RAG Document Scoping Strategy

When starting chat from project:
1. Fetch all documents in project: `SELECT document_id FROM collection_documents WHERE collection_id = ?`
2. Store in thread: `thread.rag_document_scope = {"document_ids": [...]}`
3. During RAG retrieval: Filter results to only these document IDs
4. Display to user: "Searching within X project documents"

**Alternative**: Don't store document IDs, query dynamically via `project_threads` join. Trade-off: more flexible (documents can be added/removed) but slower query.

**Recommendation**: Store document IDs at thread creation for performance. Provide "Refresh Context" button to update if project documents change.

---

## Frontend Navigation Flow

### Starting Chat from Project
1. User on `/projects/{id}` → clicks "Conversations" tab
2. Clicks "New Chat" → modal appears with message input
3. Submits → API creates conversation (if needed), thread, project_thread link
4. Navigates to `/chat?thread={thread_id}`
5. Chat UI shows: "Project Context: Research Paper | 12 documents"

### Linking Existing Thread
1. User on `/projects/{id}` → "Conversations" tab
2. Clicks "Link Existing" → thread selector modal
3. Shows threads from same workspace, not already linked
4. Selects thread → creates project_thread link
5. Thread appears in project's linked threads list

### Opening Linked Thread
1. User on `/projects/{id}` → "Conversations" tab
2. Clicks thread card → navigates to `/chat?thread={thread_id}`
3. Chat loads with project context indicator

### Saving Thread to Note
1. User in chat interface → clicks "Save to Project"
2. Project selector appears (if thread linked to multiple projects)
3. Confirms → creates new ProjectNote with thread content
4. Note appears in project's Notes tab

---

## Testing Checklist

### Unit Tests
- [ ] `test_project_thread_model.py` - Model validation
- [ ] `test_project_chat_api.py` - API endpoints

### Integration Tests
- [ ] Create project → Add documents → Start chat → Verify RAG context
- [ ] Link existing thread → Verify appears in project
- [ ] Unlink thread → Verify removed from project
- [ ] Save thread to note → Verify note created with content
- [ ] Delete project → Verify project_threads cascade deleted

### E2E Tests
- [ ] Full flow: Project → New Chat → Ask question → Verify citations from project docs only
- [ ] Verify project context indicator in chat UI
- [ ] Verify thread appears in project Conversations tab
- [ ] Verify workspace boundary enforcement

---

## Migration Strategy

### Alembic Migration
```python
def upgrade():
    op.create_table(
        'project_threads',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('project_id', GUID(), nullable=False),
        sa.Column('thread_id', GUID(), nullable=False),
        sa.Column('link_type', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('linked_by_id', GUID(), nullable=True),
        sa.Column('context_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_by_id'], ['users.id']),
        sa.UniqueConstraint('project_id', 'thread_id')
    )
    op.create_index('idx_project_threads_project_id', 'project_threads', ['project_id'])
    op.create_index('idx_project_threads_thread_id', 'project_threads', ['thread_id'])
    
    # Optional: Add columns to threads table
    op.add_column('threads', sa.Column('source_project_id', GUID(), nullable=True))
    op.add_column('threads', sa.Column('rag_document_scope', JSONB, nullable=True))
    op.create_foreign_key('fk_threads_source_project', 'threads', 'collections', ['source_project_id'], ['id'], ondelete='SET NULL')

def downgrade():
    op.drop_constraint('fk_threads_source_project', 'threads')
    op.drop_column('threads', 'rag_document_scope')
    op.drop_column('threads', 'source_project_id')
    op.drop_index('idx_project_threads_thread_id', 'project_threads')
    op.drop_index('idx_project_threads_project_id', 'project_threads')
    op.drop_table('project_threads')
```

---

## File Checklist

### Backend - Create
- [ ] `backend/src/models/project_thread.py`
- [ ] `backend/src/api/research/project_chat.py`
- [ ] `backend/alembic/versions/XXXX_add_project_thread_table.py`
- [ ] `backend/tests/test_project_thread_model.py`
- [ ] `backend/tests/test_project_chat_api.py`

### Backend - Modify
- [ ] `backend/src/models/__init__.py`
- [ ] `backend/src/models/thread.py`
- [ ] `backend/src/api/threads/threads.py`
- [ ] `backend/src/shared/research_schemas.py`
- [ ] `backend/src/main.py`

### Frontend - Create
- [ ] `frontend/src/services/projectChatService.ts`
- [ ] `frontend/src/types/project-chat.ts`
- [ ] `frontend/src/components/research/ProjectChatTab.tsx`

### Frontend - Modify
- [ ] `frontend/src/store/projectStore.ts`
- [ ] `frontend/app/(dashboard)/projects/[id]/page.tsx`
- [ ] `frontend/app/(dashboard)/chat/page.tsx`

---

## Success Metrics

1. **Functional**: User can start chat from project and ask questions scoped to project documents
2. **Performance**: RAG retrieval filtered by document scope completes in <2s
3. **UX**: Seamless navigation between projects and chat with context preservation
4. **Data Integrity**: No orphaned project_threads after project/thread deletion

---

## Future Enhancements (Post-MVP)

1. **Auto-link Intelligence**: Automatically suggest projects when user asks about specific topics
2. **Multi-project Context**: Allow thread to be linked to multiple projects
3. **Citation to Project**: Automatically link documents cited in chat to relevant projects
4. **Project Chat Analytics**: Track which projects generate most questions, citation patterns
5. **Collaborative Projects**: Share project-linked threads with team members
