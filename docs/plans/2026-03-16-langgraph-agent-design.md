# LangGraph Agent Integration — Design Document

**Date:** 2026-03-16
**Status:** Approved

## Summary

Replace the manual tool-calling loop in the agent endpoint with a LangGraph StateGraph. Adds multi-step reasoning, conditional routing, PostgreSQL checkpointing, and async job execution with frontend polling.

## Scope

Replace only `POST /api/v1/agent/execute` internals. Everything else stays — FastAPI routes, thread persistence, frontend components, Zustand store, `/chat/completions`.

## Architecture

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  rag_node   │  Hybrid search, org-scoped
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  llm_node   │  Azure OpenAI gpt-4o with tools
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─no──┤ has_tools?  ├──yes─┐
              │     └─────────────┘      │
              │                   ┌──────▼──────┐
              │                   │  tool_node  │  Execute tools
              │                   └──────┬──────┘
              │                          │
              │                   (loop back to llm_node, max 10)
              │
       ┌──────▼──────┐
       │     END     │  Return final response
       └─────────────┘
```

## State Schema

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangGraph message accumulator
    page_context: dict                        # {type, project_id, ...}
    retrieved_contexts: list                  # RAG results for citations
    tool_executions: list                     # Tool results for frontend display
    thread_id: str                            # For persistence
```

## Async Job System

### Endpoints

| Endpoint                          | Method | Purpose                                               |
| --------------------------------- | ------ | ----------------------------------------------------- |
| `POST /api/v1/agent/execute`      | Start  | Returns `{job_id}` immediately                        |
| `GET /api/v1/agent/jobs/{job_id}` | Poll   | Returns `{status, result?, tool_executions?, error?}` |

### Job Lifecycle

```
POST /execute
  → Create job record (in-memory dict with TTL)
  → Run graph in FastAPI BackgroundTask
  → Return {job_id}

Frontend polls GET /jobs/{job_id} every 1-2s:
  → status: "running" + tool_executions so far
  → status: "completed" + final result + all tool_executions
  → status: "failed" + error
```

Jobs are ephemeral (in-memory with cleanup). Thread/messages persist to PostgreSQL as before.

## Tool Wrapping

Existing tool implementations reused. Wrapped as LangGraph `@tool` functions:

```python
@tool
async def search_arxiv(query: str, max_results: int = 5) -> dict:
    """Search arXiv for academic papers."""
    ...
```

`db` and `current_user` passed via `RunnableConfig`:

```python
config = {"configurable": {"db": db, "current_user": current_user}}
result = await graph.ainvoke(state, config=config)
```

### Tools (6 total)

| Tool                      | Purpose                         |
| ------------------------- | ------------------------------- |
| `search_arxiv`            | Search ArXiv for papers         |
| `ingest_arxiv_papers`     | Download & index papers         |
| `search_documents`        | Search user's indexed documents |
| `add_document_to_project` | Link document to project        |
| `create_project_note`     | Create markdown note in project |
| `list_project_documents`  | List project documents          |

`project_id` auto-filled from page context in tool_node when not provided by LLM.

## LLM Provider

Azure OpenAI via `langchain-openai` `AzureChatOpenAI`. Same credentials/deployment as current `azure_openai_service`.

## Checkpointing

PostgreSQL checkpointer from `langgraph-checkpoint-postgres`. Reuses existing database connection. Enables:

- State recovery on failure
- Conversation continuity across requests
- Debugging/observability of graph execution

## New Dependencies

```
langgraph>=0.4
langchain-openai>=0.3
langchain-core>=0.3
langgraph-checkpoint-postgres>=0.1
```

## File Structure

### New Files

```
backend/src/services/agent/
├── __init__.py
├── graph.py          # StateGraph definition
├── state.py          # AgentState TypedDict
├── tools.py          # 6 @tool wrapped functions
└── checkpointer.py   # PostgreSQL checkpointer setup
```

### Modified Files

```
backend/src/api/agent/execute.py
  - POST /execute → async job + graph invocation
  - GET /jobs/{job_id} → poll endpoint
  - Remove manual tool loop
  - Keep: schemas, thread persistence, system prompt

frontend/src/services/agentChatService.ts
  - execute() returns {job_id}
  - New pollJob(jobId) method

frontend/src/store/agentChatStore.ts
  - sendMessage() → poll loop
  - Progressive tool_executions updates

backend/requirements.txt
  - Add langgraph, langchain-openai, langchain-core, langgraph-checkpoint-postgres
```

### Unchanged

- All frontend UI components
- usePageContext hook
- Thread/message persistence logic
- `/chat/completions` endpoint
- Docker Compose setup
- All existing tests

## Safety

- Max 10 tool iterations per graph invocation (prevent infinite loops)
- Job TTL cleanup (1 hour, prevent memory leak)
- All existing auth/IDOR checks preserved in tool implementations
- Role validation on messages (user/assistant only)
- Org-scoped RAG retrieval unchanged
