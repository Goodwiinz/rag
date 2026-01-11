# Thread Workflow Analysis - Multimodal Enterprise RAG System

## Executive Summary

The thread workflow is a hierarchical chat persistence system following the pattern:

```
Workspace → Conversation → Thread → Message (with Citations)
```

This architecture enables granular organization of user-AI interactions with RAG-powered citations.

---

## 1. Data Model Hierarchy

### 1.1 Entity Relationship

```
WORKSPACE (1) ──► (N) CONVERSATION (1) ──► (N) THREAD (1) ──► (N) CHAT_MESSAGE (1) ──► (N) CITATION
```

**Key Relationships:**
- `Workspace` contains multiple `Conversation`s
- `Conversation` contains multiple `Thread`s (specific lines of inquiry)
- `Thread` contains multiple `ChatMessage`s (user/assistant exchanges)
- `ChatMessage` can have multiple `Citation`s (RAG sources)

### 1.2 Thread Model (`backend/src/models/thread.py:19-115`)

```python
class Thread(BaseModel):
    __tablename__ = "threads"
    
    # Parent relationship
    conversation_id = Column(GUID(), ForeignKey("conversations.id", ondelete="CASCADE"))
    
    # Basic info
    title = Column(String(500), nullable=True)  # Optional, auto-generated
    summary = Column(Text, nullable=True)        # AI-generated
    
    # Status: ACTIVE | RESOLVED | ARCHIVED
    status = Column(Enum(ThreadStatus), default=ThreadStatus.ACTIVE)
    
    # Metrics
    last_message_at = Column(DateTime(timezone=True))
    message_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="threads")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")
```

### 1.3 Thread Status States

- **ACTIVE**: Default state, can send/receive messages
- **RESOLVED**: Investigation complete, can be reopened
- **ARCHIVED**: Hidden from default views

---

## 2. Backend Architecture

### 2.1 API Endpoints (`backend/src/api/threads.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/threads` | POST | Create new thread |
| `/api/v2/threads` | GET | List threads for conversation |
| `/api/v2/threads/{id}` | GET | Get thread details |
| `/api/v2/threads/{id}` | PUT | Update thread |
| `/api/v2/threads/{id}` | DELETE | Delete thread |
| `/api/v2/threads/{id}/resolve` | POST | Mark as resolved |
| `/api/v2/threads/{id}/reopen` | POST | Reopen resolved thread |
| `/api/v2/threads/{id}/archive` | POST | Archive thread |
| `/api/v2/threads/{id}/context` | GET | Get LLM context (for RAG) |
| `/api/v2/threads/{id}/messages` | POST | Create message |
| `/api/v2/threads/{id}/messages` | GET | List messages |

### 2.2 ChatService Methods (`backend/src/services/chat_service.py`)

**Thread Operations:**
- `create_thread(data, user_id)` - Create thread with optional initial message
- `get_thread(thread_id, user_id, include_messages=False)` - Get thread
- `list_threads(conversation_id, user_id)` - List threads in conversation
- `update_thread(thread_id, user_id, data)` - Update thread
- `delete_thread(thread_id, user_id)` - Delete thread

**Message Operations:**
- `create_message(data, user_id)` - Create message with citations/attachments
- `create_assistant_message(thread_id, content, citations, ...)` - AI response
- `get_thread_context(thread_id, user_id, max_messages=20, max_tokens=4000)` - LLM context

### 2.3 Thread Creation Flow

```python
def create_thread(data, user_id):
    # 1. Verify conversation access
    conversation = self.get_conversation(data.conversation_id, user_id)
    
    # 2. Check edit permission
    if not conversation.workspace.can_user_edit(str(user_id)):
        return None
    
    # 3. Create thread
    thread = Thread(
        conversation_id=data.conversation_id,
        title=data.title,
        status=ThreadStatus.ACTIVE,
        created_by_id=user_id
    )
    
    # 4. Optional initial message
    if data.initial_message:
        initial_msg = ChatMessage.create_user_message(thread_id=thread.id, ...)
        
    # 5. Update conversation activity
    conversation.update_activity()
    
    return thread
```

### 2.4 Message with Citations

```python
def create_message(data, user_id):
    message = ChatMessage(thread_id=data.thread_id, role=data.role, content=data.content)
    
    # Handle attachments (documents)
    for doc_id in data.attachment_ids:
        attachment = MessageAttachment(message_id=message.id, document_id=doc_id)
        
    # Handle citations (RAG sources)
    for cit in data.citations:
        citation = Citation(
            message_id=message.id,
            document_id=cit.document_id,
            chunk_index=cit.chunk_index,
            snippet=cit.snippet,
            score=cit.score,
            rerank_score=cit.rerank_score
        )
    
    # Update thread stats
    thread.message_count += 1
    thread.last_message_at = datetime.utcnow()
```

---

## 3. Frontend Architecture

### 3.1 Type Definitions (`frontend/src/types/workspace.ts`)

```typescript
enum ThreadStatus {
  ACTIVE = 'active',
  RESOLVED = 'resolved',
  ARCHIVED = 'archived',
}

interface Thread {
  id: string;
  conversation_id: string;
  title: string;
  summary?: string;
  status: ThreadStatus;
  last_message_at: string;
  message_count: number;
  token_count: number;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

interface ChatMessage {
  id: string;
  thread_id: string;
  user_id?: string;
  content: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  token_count?: number;
  citations?: Citation[];
  attachments?: MessageAttachment[];
  created_at: string;
}

interface Citation {
  id: string;
  document_id?: string;
  external_reference_id?: string;
  chunk_index?: number;
  snippet: string;
  snippet_preview?: string;
  score?: number;
  rerank_score?: number;
  document_title?: string;
  document_type?: string;
}
```

### 3.2 State Management (`frontend/src/store/chat-store.ts`)

**State Shape:**
```typescript
interface ChatState {
  // Selection state
  currentWorkspaceId: string | null;
  currentConversationId: string | null;
  currentThreadId: string | null;
  
  // Data (keyed by parent ID)
  workspaces: Workspace[];
  conversations: Record<string, Conversation[]>;  // workspaceId → conversations
  threads: Record<string, Thread[]>;              // conversationId → threads
  messages: Record<string, ChatMessage[]>;        // threadId → messages
  
  // Loading states
  isLoadingWorkspaces/Conversations/Threads/Messages: boolean;
  isSendingMessage: boolean;
  isReinitializing: boolean;
  reinitRetryCount: number;
  error: string | null;
}
```

**Key Actions:**
```typescript
interface ChatActions {
  // Selection (cascade loading)
  setCurrentWorkspace: (id) => void;      // → loadConversations
  setCurrentConversation: (id) => void;   // → loadThreads
  setCurrentThread: (id) => void;         // → loadMessages
  
  // Thread CRUD
  loadThreads: (conversationId) => Promise<void>;
  createThread: (data) => Promise<Thread>;
  updateThread: (id, data) => Promise<Thread>;
  deleteThread: (id) => Promise<boolean>;
  resolveThread: (id) => Promise<Thread>;
  reopenThread: (id) => Promise<Thread>;
  
  // Messages
  sendMessage: (content, threadId?) => Promise<ChatMessage>;
  loadMessages: (threadId) => Promise<void>;
  
  // Recovery
  initializeDefaultWorkspace: () => Promise<void>;
}
```

### 3.3 Bridge Hook (`frontend/src/hooks/useChatPersistence.ts`)

Maps internal Thread/Message types to UI-friendly formats:

```typescript
function useChatPersistence(): UseChatPersistenceReturn {
  // Map threads to UIConversation format
  const uiConversations = useMemo(() => 
    threads[currentConversationId].map(thread => mapThreadToUIConversation(thread)),
    [threads, currentConversationId]
  );
  
  return {
    isInitialized,
    isLoading,
    conversations: uiConversations,
    messages: currentMessages,
    
    createNewChat: async () => {
      // Auto-create workspace/conversation if needed
      if (!conversationId) {
        const conv = await createConversation({ workspace_id, title: 'New Chat' });
      }
      const thread = await createThread({ conversation_id: conversationId });
      return thread.id;
    },
    
    sendMessage: async (content) => {
      // Auto-create thread if needed
      if (!currentThreadId) {
        const thread = await createThread({ 
          conversation_id: currentConversationId,
          title: content.substring(0, 50)
        });
      }
      return storeSendMessage(content, threadId);
    },
    
    selectConversation: (id) => setCurrentThread(id),
    deleteConversation: (id) => deleteThread(id),
    renameConversation: (id, title) => updateThread(id, { title }),
    archiveConversation: (id) => updateThread(id, { status: ThreadStatus.ARCHIVED }),
  };
}
```

### 3.4 API Service (`frontend/src/services/workspaceService.ts`)

```typescript
const workspaceService = {
  createThread: (data) => v2Client.post('/api/v2/threads', data),
  getThread: (id) => v2Client.get(`/api/v2/threads/${id}`),
  listThreads: (conversationId) => v2Client.get(`/api/v2/conversations/${conversationId}/threads`),
  updateThread: (id, data) => v2Client.patch(`/api/v2/threads/${id}`, data),
  deleteThread: (id) => v2Client.delete(`/api/v2/threads/${id}`),
  
  createMessage: (data) => v2Client.post('/api/v2/messages', data),
  listMessages: (threadId) => v2Client.get(`/api/v2/threads/${threadId}/messages`),
};
```

---

## 4. Data Flow

### 4.1 Thread Creation Flow

```
User clicks "New Chat"
    │
    ▼
useChatPersistence.createNewChat()
    │
    ├── (if no conversation) createConversation()
    │
    ▼
chat-store.createThread()
    │
    ▼
workspaceService.createThread()
    │
    ▼
POST /api/v2/threads
    │
    ▼
ChatService.create_thread()
    │
    ├── Verify conversation access
    ├── Check edit permission
    ├── Create Thread record
    ├── Optional: Create initial message
    └── Update conversation.last_activity_at
    │
    ▼
Return Thread → Update store → Select thread → Load messages
```

### 4.2 Send Message with RAG Flow

```
User submits message
    │
    ▼
chat-store.sendMessage(content, threadId)
    │
    ├── (if no thread) createThread()
    │
    ▼
workspaceService.createMessage()
    │
    ▼
POST /api/v2/threads/{id}/messages
    │
    ▼
ChatService.create_message()
    │
    ▼
RAG Pipeline:
    ├── Hybrid Search (Vector + Graph + Keyword)
    ├── Reranker (CrossEncoder)
    └── Multi-Agent Orchestration (CrewAI)
    │
    ▼
ChatService.create_assistant_message()
    │
    ├── Create ChatMessage (role=assistant)
    ├── Attach Citations (document sources with scores)
    └── Update thread stats
    │
    ▼
Return message with citations → Update store → Render in UI
```

---

## 5. Error Recovery

### 5.1 Stale Data Recovery Pattern

Handles 404 errors from cached IDs pointing to deleted resources:

```typescript
function handleStaleDataRecovery(get, set, context, options) {
  // Guard against concurrent/infinite reinitializations
  if (state.isReinitializing || state.reinitRetryCount >= MAX_REINIT_RETRIES) {
    return { shouldProceed: false };
  }
  
  // Atomically clear stale data + set reinit flag
  set((state) => {
    state.currentWorkspaceId = null;
    state.currentConversationId = null;
    state.currentThreadId = null;
    state.workspaces = [];
    state.isReinitializing = true;
    state.reinitRetryCount += 1;
  });
  
  return {
    shouldProceed: true,
    triggerReinit: () => get().initializeDefaultWorkspace()
  };
}
```

### 5.2 State Persistence

```typescript
// Zustand persist middleware - only IDs persisted, data reloaded
persist(store, {
  name: 'chat-storage',
  partialize: (state) => ({
    currentWorkspaceId: state.currentWorkspaceId,
    currentConversationId: state.currentConversationId,
    currentThreadId: state.currentThreadId,
    sidebarCollapsed: state.sidebarCollapsed,
  }),
});
```

---

## 6. Key Files Reference

### Backend
| File | Line | Purpose |
|------|------|---------|
| `backend/src/models/thread.py` | 19-115 | Thread SQLAlchemy model |
| `backend/src/models/chat_message.py` | 20-178 | ChatMessage model |
| `backend/src/models/citation.py` | 10-88 | Citation model |
| `backend/src/api/threads.py` | 39-72 | Thread API endpoints |
| `backend/src/services/chat_service.py` | 344-387 | create_thread() |
| `backend/src/services/chat_service.py` | 502-563 | create_message() |
| `backend/src/services/chat_service.py` | 895-931 | get_thread_context() |
| `backend/src/schemas/chat.py` | 23-27 | ThreadStatus enum |

### Frontend
| File | Line | Purpose |
|------|------|---------|
| `frontend/src/types/workspace.ts` | 16-20 | ThreadStatus enum |
| `frontend/src/types/workspace.ts` | 135-147 | Thread interface |
| `frontend/src/types/workspace.ts` | 218-236 | ChatMessage interface |
| `frontend/src/types/workspace.ts` | 165-178 | Citation interface |
| `frontend/src/store/chat-store.ts` | 472-508 | loadThreads, createThread |
| `frontend/src/store/chat-store.ts` | 610-647 | sendMessage |
| `frontend/src/hooks/useChatPersistence.ts` | 150-428 | Bridge hook |
| `frontend/src/services/workspaceService.ts` | 220-223 | API client |

---

## 7. Design Patterns

1. **Repository Pattern**: SQLAlchemy models with business methods
2. **Service Layer**: ChatService encapsulates all business logic
3. **Bridge Hook Pattern**: useChatPersistence maps store→UI types
4. **Immer Middleware**: Immutable state updates with mutable syntax
5. **Cascade Loading**: Selection changes trigger child data loading
6. **Optimistic Updates**: UI updates before server confirmation
7. **Stale Data Recovery**: 404 handling with reinit + retry limits

---

## 8. Thread Auto-Title Generation

```python
def generate_title(self) -> str:
    """Generate title from first user message (50 chars max)"""
    for msg in self.messages:
        if msg.role == MessageRole.USER and msg.content:
            title = msg.content[:50]
            if len(msg.content) > 50:
                title += "..."
            return title
    return f"Thread {str(self.id)[:8]}"
```

---

*Last updated: 2026-01-10*
