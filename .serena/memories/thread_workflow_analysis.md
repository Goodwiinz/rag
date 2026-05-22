# Thread/Chat Workflow

## Hierarchy
Workspace → Conversation → Thread → Message (with Citations)

## Backend
- Models: Thread, ChatMessage, Citation (backend/src/models/)
- Service: ChatService (backend/src/services/chat_service.py)
- APIs: /api/v2/threads (CRUD, resolve, reopen, archive, messages)

## Thread Status: ACTIVE | RESOLVED | ARCHIVED

## Key Flows
1. **Create thread**: validate conversation → check edit perm → create thread → optional initial message → update conversation activity
2. **Send message**: create ChatMessage → RAG pipeline (hybrid search + rerank) → create assistant message with citations → update thread stats
3. **Get context**: GET /threads/{id}/context → last 20 messages, max 4000 tokens (for LLM context window)

## Frontend
- Store: chat-store.ts (Zustand + immer + persist)
- Bridge hook: useChatPersistence.ts (maps Thread/Message → UI types)
- Service: workspaceService.ts
- Selection cascade: workspace → loadConversations → loadThreads → loadMessages
- Stale data recovery: 404 → clear cached IDs → reinit (max 3 retries)

## Citations
- document_id nullable (supports external refs like ArXiv via external_reference_id)
- Fields: snippet, score, rerank_score, document_title, document_type
