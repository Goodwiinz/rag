# Agent Tool Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 4 new agent tools (search_documents, add_document_to_project, create_project_note, list_project_documents) and fix the ingest tool to return document IDs.

**Architecture:** Direct service calls from within the agent endpoint. All tools share `db` session and `current_user` from FastAPI DI. Single file change (`execute.py`) plus model imports.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, OpenAI function calling

**Design doc:** `docs/plans/2026-03-16-agent-tool-expansion-design.md`

---

## Task 1: Update execute_tool Signature & Pass DB/User

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Update `execute_tool` signature**

Change line 140 from:

```python
async def execute_tool(tool_name: str, args: Dict[str, Any], user_id: str = "") -> Dict[str, Any]:
```

to:

```python
async def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    user_id: str = "",
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
```

**Step 2: Update the call site in `execute_agent`**

Find the line (around 340):

```python
tool_result = await execute_tool(tool_name, tool_args, user_id=str(current_user.id))
```

Change to:

```python
tool_result = await execute_tool(
    tool_name, tool_args,
    user_id=str(current_user.id),
    db=db,
    current_user=current_user,
)
```

**Step 3: Verify backend starts**

Run: `docker compose -f docker-compose.development.yml restart backend`
Check: `curl -s http://localhost:8000/api/v1/agent/health` returns `{"status":"ok"}`

**Step 4: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "refactor(agent): pass db and current_user to execute_tool"
```

---

## Task 2: Add search_documents Tool

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Add tool definition to AGENT_TOOLS list**

Add after the `ingest_arxiv_papers` entry in the AGENT_TOOLS list:

```python
{
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the user's indexed documents by title or content. Use when the user asks to find, look up, or search their existing documents (not arXiv).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to match against document titles and content",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results (1-20, default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
},
```

**Step 2: Add tool implementation**

Add after `_tool_ingest_arxiv`:

```python
async def _tool_search_documents(
    args: Dict[str, Any], db: AsyncSession, current_user: User
) -> Dict[str, Any]:
    """Search the user's indexed documents."""
    from src.models.document import Document

    query_text = args.get("query", "")
    max_results = min(args.get("max_results", 10), 20)

    if not query_text:
        return {"error": "No search query provided"}

    try:
        stmt = (
            select(Document)
            .where(
                Document.organization_id == current_user.organization_id,
                Document.is_deleted == False,
                Document.title.ilike(f"%{query_text}%")
                | Document.filename.ilike(f"%{query_text}%"),
            )
            .order_by(desc(Document.created_at))
            .limit(max_results)
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()

        return {
            "documents": [
                {
                    "id": str(d.id),
                    "title": d.title or d.filename or "Untitled",
                    "type": d.document_type.value if d.document_type else "unknown",
                    "status": d.processing_status.value if d.processing_status else "unknown",
                    "created_at": d.created_at.isoformat() if d.created_at else "",
                }
                for d in docs
            ],
            "total": len(docs),
            "query": query_text,
        }
    except Exception as e:
        logger.error("Document search tool failed", exc_info=e)
        return {"error": f"Search failed: {str(e)}"}
```

**Step 3: Register in execute_tool**

Add to the `execute_tool` function:

```python
if tool_name == "search_documents":
    return await _tool_search_documents(args, db, current_user)
```

**Step 4: Add import**

At the top of `execute.py`, add to existing imports:

```python
from src.models.document import Document
```

**Step 5: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`
Test: Send "search my documents for deep learning" in the agent panel

**Step 6: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent): add search_documents tool"
```

---

## Task 3: Add add_document_to_project Tool

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Add tool definition**

```python
{
    "type": "function",
    "function": {
        "name": "add_document_to_project",
        "description": "Add an existing document to a research project. Use when the user wants to link, add, or include a document in their project. Requires document_id. Uses current project from page context if project_id not provided.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "UUID of the document to add",
                },
                "project_id": {
                    "type": "string",
                    "description": "UUID of the project. Optional if user is on a project page.",
                },
            },
            "required": ["document_id"],
        },
    },
},
```

**Step 2: Add tool implementation**

```python
async def _tool_add_document_to_project(
    args: Dict[str, Any], db: AsyncSession, current_user: User
) -> Dict[str, Any]:
    """Add a document to a research project."""
    from src.models.collection import Collection, CollectionDocument

    doc_id = args.get("document_id")
    project_id = args.get("project_id")

    if not doc_id:
        return {"error": "document_id is required"}
    if not project_id:
        return {"error": "project_id is required (or navigate to a project page)"}

    try:
        # Verify document exists and belongs to user's org
        doc = await db.get(Document, UUID(doc_id))
        if not doc or doc.organization_id != current_user.organization_id:
            return {"error": f"Document {doc_id} not found"}

        # Verify project exists and belongs to user
        project_stmt = (
            select(Collection)
            .join(Workspace, Collection.workspace_id == Workspace.id)
            .where(
                Collection.id == UUID(project_id),
                Workspace.owner_id == current_user.id,
            )
        )
        project_result = await db.execute(project_stmt)
        project = project_result.scalar_one_or_none()
        if not project:
            return {"error": f"Project {project_id} not found"}

        # Check if already linked
        existing_stmt = select(CollectionDocument).where(
            CollectionDocument.collection_id == UUID(project_id),
            CollectionDocument.document_id == UUID(doc_id),
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            return {
                "status": "already_linked",
                "message": f"'{doc.title or doc.filename}' is already in '{project.name}'",
            }

        # Create link
        link = CollectionDocument(
            collection_id=UUID(project_id),
            document_id=UUID(doc_id),
        )
        db.add(link)
        await db.commit()

        return {
            "status": "added",
            "document_title": doc.title or doc.filename or "Untitled",
            "project_name": project.name,
            "message": f"Added '{doc.title or doc.filename}' to '{project.name}'",
        }
    except Exception as e:
        logger.error("Add document to project tool failed", exc_info=e)
        await db.rollback()
        return {"error": f"Failed to add document: {str(e)}"}
```

**Step 3: Register in execute_tool**

```python
if tool_name == "add_document_to_project":
    return await _tool_add_document_to_project(args, db, current_user)
```

**Step 4: Add model imports**

```python
from src.models.collection import Collection, CollectionDocument
```

**Step 5: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`

**Step 6: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent): add add_document_to_project tool"
```

---

## Task 4: Add create_project_note Tool

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Add tool definition**

```python
{
    "type": "function",
    "function": {
        "name": "create_project_note",
        "description": "Create a markdown note in a research project. Use when the user asks to create a note, write a summary, save observations, or document findings.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "UUID of the project. Optional if user is on a project page.",
                },
                "title": {
                    "type": "string",
                    "description": "Note title",
                },
                "content": {
                    "type": "string",
                    "description": "Note content in markdown format",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for the note",
                },
            },
            "required": ["title", "content"],
        },
    },
},
```

**Step 2: Add tool implementation**

```python
async def _tool_create_project_note(
    args: Dict[str, Any], db: AsyncSession, current_user: User
) -> Dict[str, Any]:
    """Create a note in a research project."""
    from src.models.project_note import ProjectNote

    project_id = args.get("project_id")
    title = args.get("title", "")
    content = args.get("content", "")
    tags = args.get("tags", [])

    if not title or not content:
        return {"error": "title and content are required"}
    if not project_id:
        return {"error": "project_id is required (or navigate to a project page)"}

    try:
        # Verify project exists and belongs to user
        project_stmt = (
            select(Collection)
            .join(Workspace, Collection.workspace_id == Workspace.id)
            .where(
                Collection.id == UUID(project_id),
                Workspace.owner_id == current_user.id,
            )
        )
        project_result = await db.execute(project_stmt)
        project = project_result.scalar_one_or_none()
        if not project:
            return {"error": f"Project {project_id} not found"}

        note = ProjectNote(
            project_id=UUID(project_id),
            user_id=current_user.id,
            title=title,
            content=content,
            tags=tags,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        return {
            "status": "created",
            "note_id": str(note.id),
            "title": title,
            "project_name": project.name,
            "message": f"Created note '{title}' in '{project.name}'",
        }
    except Exception as e:
        logger.error("Create project note tool failed", exc_info=e)
        await db.rollback()
        return {"error": f"Failed to create note: {str(e)}"}
```

**Step 3: Register in execute_tool**

```python
if tool_name == "create_project_note":
    return await _tool_create_project_note(args, db, current_user)
```

**Step 4: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`

**Step 5: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent): add create_project_note tool"
```

---

## Task 5: Add list_project_documents Tool

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Add tool definition**

```python
{
    "type": "function",
    "function": {
        "name": "list_project_documents",
        "description": "List all documents in a research project. Use when the user asks what documents are in their project, or wants to see the project contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "UUID of the project. Optional if user is on a project page.",
                },
            },
            "required": [],
        },
    },
},
```

**Step 2: Add tool implementation**

```python
async def _tool_list_project_documents(
    args: Dict[str, Any], db: AsyncSession, current_user: User
) -> Dict[str, Any]:
    """List documents in a research project."""
    project_id = args.get("project_id")

    if not project_id:
        return {"error": "project_id is required (or navigate to a project page)"}

    try:
        # Verify project ownership
        project_stmt = (
            select(Collection)
            .join(Workspace, Collection.workspace_id == Workspace.id)
            .where(
                Collection.id == UUID(project_id),
                Workspace.owner_id == current_user.id,
            )
        )
        project_result = await db.execute(project_stmt)
        project = project_result.scalar_one_or_none()
        if not project:
            return {"error": f"Project {project_id} not found"}

        # Get documents
        docs_stmt = (
            select(Document)
            .join(CollectionDocument, CollectionDocument.document_id == Document.id)
            .where(CollectionDocument.collection_id == UUID(project_id))
            .order_by(Document.created_at.desc())
        )
        docs_result = await db.execute(docs_stmt)
        docs = docs_result.scalars().all()

        return {
            "project_name": project.name,
            "documents": [
                {
                    "id": str(d.id),
                    "title": d.title or d.filename or "Untitled",
                    "type": d.document_type.value if d.document_type else "unknown",
                    "status": d.processing_status.value if d.processing_status else "unknown",
                }
                for d in docs
            ],
            "total": len(docs),
        }
    except Exception as e:
        logger.error("List project documents tool failed", exc_info=e)
        return {"error": f"Failed to list documents: {str(e)}"}
```

**Step 3: Register in execute_tool**

```python
if tool_name == "list_project_documents":
    return await _tool_list_project_documents(args, db, current_user)
```

**Step 4: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`

**Step 5: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent): add list_project_documents tool"
```

---

## Task 6: Fix ingest_arxiv_papers to Return Document IDs

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Update `_tool_ingest_arxiv` to return document IDs**

Replace the return block in `_tool_ingest_arxiv` (after `service.ingest_papers`):

```python
            ingested = await service.ingest_papers(
                papers=papers_to_ingest,
                download_pdfs=True,
                extract_content=True,
            )

            # Extract document IDs from returned objects
            document_ids = []
            if ingested:
                for doc in ingested:
                    doc_id = getattr(doc, "id", None)
                    if doc_id:
                        document_ids.append(str(doc_id))

            return {
                "status": "ingestion_complete",
                "paper_ids": paper_ids,
                "document_ids": document_ids,
                "ingested_count": len(document_ids),
                "message": f"Ingested {len(document_ids)} paper(s). Document IDs: {document_ids}",
            }
```

**Step 2: Restart and verify**

Run: `docker compose -f docker-compose.development.yml restart backend`

**Step 3: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "fix(agent): return document_ids from ingest tool for chaining"
```

---

## Task 7: Update System Prompt & Integration Test

**Files:**

- Modify: `backend/src/api/agent/execute.py`

**Step 1: Update system prompt to list all tools**

Update `build_agent_system_prompt` to include:

```python
    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

You have access to these tools:
- search_arxiv: Search arXiv for academic papers
- ingest_arxiv_papers: Download and index arXiv papers into the system
- search_documents: Search the user's indexed documents
- add_document_to_project: Add a document to a research project
- create_project_note: Create a markdown note in a project
- list_project_documents: List documents in a project

When the user asks to find papers, use search_arxiv. When they want to add papers to their system, use ingest_arxiv_papers, then add_document_to_project to link them.
When on a project page, you know the project_id from the page context — use it automatically.

{context_line}

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""
```

**Step 2: Restart backend**

Run: `docker compose -f docker-compose.development.yml restart backend`

**Step 3: End-to-end test**

Open agent panel on a project page. Try:

1. "What documents are in this project?" → should use `list_project_documents`
2. "Search my documents for deep learning" → should use `search_documents`
3. "Create a note titled 'Research Summary' with content about the project" → should use `create_project_note`

**Step 4: Commit**

```bash
git add backend/src/api/agent/execute.py
git commit -m "feat(agent): update system prompt with full tool list, integration test"
```

---

## Summary

| Task | Tool                      | What                                   |
| ---- | ------------------------- | -------------------------------------- |
| 1    | —                         | Pass db/current_user to execute_tool   |
| 2    | `search_documents`        | Search indexed docs by title           |
| 3    | `add_document_to_project` | Link document to project               |
| 4    | `create_project_note`     | Create markdown note                   |
| 5    | `list_project_documents`  | List project docs                      |
| 6    | `ingest_arxiv_papers`     | Fix: return document IDs               |
| 7    | —                         | Update system prompt, integration test |
