# Agent Tool Expansion — Design Document

**Date:** 2026-03-16
**Status:** Approved

## Summary

Add 4 new tools to the Global Agent Chat and fix the existing `ingest_arxiv_papers` tool. Enables end-to-end workflows: search papers, ingest, add to project, search indexed documents, and create notes — all through natural language.

## Approach

Direct service calls from within the agent endpoint. No HTTP round-trips. Tools share the same `db` session and `current_user` from FastAPI dependency injection.

## New Tools

| Tool                      | Trigger Examples                                 | Args                                      |
| ------------------------- | ------------------------------------------------ | ----------------------------------------- |
| `search_documents`        | "find docs about X", "which documents mention Y" | `query`, `max_results?`, `document_type?` |
| `add_document_to_project` | "add this to my project"                         | `document_id`, `project_id`               |
| `create_project_note`     | "create a summary note"                          | `project_id`, `title`, `content`, `tags?` |
| `list_project_documents`  | "what's in my project?"                          | `project_id`                              |

## Existing Tool Fixes

**`ingest_arxiv_papers`:**

- Return created `document_id`s so LLM can chain into `add_document_to_project`
- Pass `db` and `current_user` for proper org ownership

## Implementation

### execute_tool signature change

```python
async def execute_tool(tool_name, args, user_id="", db=None, current_user=None):
```

### search_documents

Query `Document` table with `ilike` on title/filename, filtered by `current_user.organization_id`. Return `[{id, title, type, status, created_at}]`.

### add_document_to_project

1. Validate document exists (by ID, org-scoped)
2. Validate project exists (Collection, org-scoped)
3. Check not already linked (CollectionDocument)
4. Create CollectionDocument record
5. Return success with document title + project name

Falls back to `page_context.project_id` if `project_id` not provided.

### create_project_note

1. Validate project exists (org-scoped)
2. Create ProjectNote with title, content, tags
3. Return `{id, title}`

### list_project_documents

Query `CollectionDocument` joined with `Document` for a project. Return `[{id, title, type, status}]`.

### ingest_arxiv_papers fix

After `service.ingest_papers()`, collect `document.id` from returned Document objects. Return `{document_ids: [...], ...}` so LLM can chain.

## Multi-Step Workflow Example

"Find papers on RAG and add the top 3 to my project":

1. `search_arxiv(query="RAG", max_results=3)` → paper IDs
2. `ingest_arxiv_papers(paper_ids=[...])` → document IDs
3. `add_document_to_project(document_id=X, project_id=Y)` × 3
4. LLM synthesizes: "Added 3 papers to your project"

## Files Changed

- `backend/src/api/agent/execute.py` — Add tool defs, implementations, fix execute_tool signature
- `backend/src/services/infrastructure/azure_openai_service.py` — Already supports tools (done)
- `frontend/src/components/agent-chat/ToolExecutionCard.tsx` — Already displays tool results (done)
