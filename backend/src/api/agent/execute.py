"""
Agent execution endpoint.
Wraps chat completions with tool-calling capabilities and page context injection.
"""

import asyncio
import logging
import re
import uuid as _uuid
from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.chat_message import ChatMessage, MessageRole
from src.models.citation import Citation
from src.models.collection import Collection, CollectionDocument
from src.models.conversation import Conversation
from src.models.document import Document
from src.models.project_note import ProjectNote
from src.models.thread import Thread, ThreadStatus
from src.models.user import User
from src.models.workspace import Workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# In-memory job storage (async job system)
# ---------------------------------------------------------------------------

_jobs: OrderedDict[str, dict] = OrderedDict()
_jobs_lock = Lock()
MAX_JOBS = 500


def _cleanup_jobs():
    with _jobs_lock:
        while len(_jobs) > MAX_JOBS:
            _jobs.popitem(last=False)


def _set_job(job_id: str, data: dict):
    with _jobs_lock:
        _jobs[job_id] = data
    _cleanup_jobs()


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Message role: user or assistant")
    content: str = Field(..., max_length=32000, description="Message content")


class PageContextRequest(BaseModel):
    type: str = Field(default="unknown", description="Page context type")
    project_id: Optional[str] = Field(default=None, description="Project ID if on project page")
    project_name: Optional[str] = Field(default=None, description="Project name for display")
    label: Optional[str] = Field(default=None, description="Current page label (e.g., 'Documents', 'Notes')")
    metadata: Optional[Dict[str, Any]] = None


class AgentExecuteRequest(BaseModel):
    messages: List[AgentMessage] = Field(..., max_length=50, description="Conversation messages")
    page_context: PageContextRequest = Field(default_factory=PageContextRequest)
    model: Literal["gpt-4o", "gpt-4o-mini"] = Field(default="gpt-4o")
    use_rag: bool = Field(default=True)
    max_context_docs: int = Field(default=5, ge=1, le=10)
    thread_id: Optional[str] = None


class RetrievedContextResponse(BaseModel):
    document_id: Optional[str] = None
    title: str
    content: str
    score: float


class ToolExecutionResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    args: Dict[str, Any]
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentExecuteResponse(BaseModel):
    message: AgentMessage
    model: str
    usage: Dict[str, int]
    finish_reason: str
    timestamp: str
    rag_enabled: bool = False
    retrieved_contexts: Optional[List[RetrievedContextResponse]] = None
    tool_executions: Optional[List[ToolExecutionResponse]] = None
    thread_id: str = ""
    conversation_id: str = ""


class JobStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    status: str
    result: Optional[dict] = None
    tool_executions: Optional[List[dict]] = None
    error: Optional[str] = None
    confirmation: Optional[dict] = None


# ---------------------------------------------------------------------------
# Agent Tools
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": "Search arXiv for academic papers. Use when the user asks to find, search, or look up research papers, academic publications, or scientific articles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for arXiv papers (e.g., 'transformer attention mechanisms')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-20)",
                        "default": 5,
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ArXiv categories to filter (e.g., ['cs.AI', 'cs.LG']). Optional.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ingest_arxiv_papers",
            "description": "Ingest arXiv papers into the RAG system for indexing and search. Use when the user wants to add, import, download, or ingest specific arXiv papers. Requires paper IDs (e.g., '2401.12345').",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of arXiv paper IDs to ingest (e.g., ['2401.12345', '2312.67890'])",
                    },
                },
                "required": ["paper_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search the user's indexed documents by title or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against document titles and filenames",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_document_to_project",
            "description": "Add an existing document to a research project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to add",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "The UUID of the project (collection) to add the document to. Optional if the user is on a project page.",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project_note",
            "description": "Create a markdown note in a research project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "The UUID of the project to create the note in",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the note",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content of the note",
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
    {
        "type": "function",
        "function": {
            "name": "list_project_documents",
            "description": "List all documents in a research project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "The UUID of the project. Optional if the user is on a project page.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "Summarize a document's content. Use when the user asks for a summary or overview of a specific document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to summarize",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_documents",
            "description": "Compare multiple documents to find similarities, differences, and shared themes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document UUIDs to compare (2-5 documents)",
                    },
                    "type": {
                        "type": "string",
                        "description": "Comparison type: 'general', 'methodology', 'findings', 'themes'",
                        "default": "general",
                    },
                },
                "required": ["document_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_entities",
            "description": "Extract named entities (people, organizations, concepts, etc.) from a document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to extract entities from",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_graph",
            "description": "Search the knowledge graph for entities and their relationships. Use when the user asks about concepts, people, or organizations in the research corpus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for knowledge graph entities",
                    },
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by entity types (e.g., ['PERSON', 'ORGANIZATION', 'CONCEPT']). Optional.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft",
            "description": "Generate a literature review draft for a project based on themes. Use when the user wants to create a draft, write a review, or synthesize research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "The UUID of the project. Optional if on a project page.",
                    },
                    "themes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of themes or topics to focus the draft on",
                    },
                    "style": {
                        "type": "string",
                        "description": "Writing style: 'academic', 'technical', or 'summary'",
                        "default": "academic",
                    },
                },
                "required": ["themes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_bibliography",
            "description": "Export bibliography/references for documents in a specific citation format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document UUIDs to include in the bibliography",
                    },
                    "format": {
                        "type": "string",
                        "description": "Citation format: 'bibtex', 'apa', 'ieee', or 'mla'",
                        "default": "bibtex",
                    },
                },
                "required": ["document_ids"],
            },
        },
    },
]


async def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    user_id: str = "",
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Execute an agent tool and return the result."""
    if tool_name == "search_arxiv":
        return await _tool_search_arxiv(args)
    if tool_name == "ingest_arxiv_papers":
        return await _tool_ingest_arxiv(args, user_id, db, current_user)
    if tool_name == "search_documents":
        return await _tool_search_documents(args, db, current_user)
    if tool_name == "add_document_to_project":
        return await _tool_add_document_to_project(args, db, current_user)
    if tool_name == "create_project_note":
        return await _tool_create_project_note(args, db, current_user)
    if tool_name == "list_project_documents":
        return await _tool_list_project_documents(args, db, current_user)
    if tool_name == "summarize_document":
        return await _tool_summarize_document(args, db, current_user)
    if tool_name == "compare_documents":
        return await _tool_compare_documents(args, db, current_user)
    if tool_name == "extract_entities":
        return await _tool_extract_entities(args, db, current_user)
    if tool_name == "search_knowledge_graph":
        return await _tool_search_knowledge_graph(args)
    if tool_name == "create_draft":
        return await _tool_create_draft(args, db, current_user)
    if tool_name == "export_bibliography":
        return await _tool_export_bibliography(args, db, current_user)
    return {"error": f"Unknown tool: {tool_name}"}


def _sanitize_metadata(metadata: Any) -> dict:
    """Convert datetime objects in metadata dict to ISO strings for JSON serialization."""
    if not isinstance(metadata, dict):
        return {}
    sanitized = {}
    for k, v in metadata.items():
        if isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                item.isoformat() if isinstance(item, datetime) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


async def _tool_search_arxiv(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search arXiv for papers."""
    from src.services.arxiv.arxiv_service import ArXivIngestionService

    query = args.get("query", "")
    max_results = min(args.get("max_results", 5), 20)
    categories = args.get("categories")

    try:
        async with ArXivIngestionService() as service:
            papers = await service.search_papers(
                query=query,
                max_results=max_results,
                categories=categories,
                sort_by="relevance",
                sort_order="descending",
            )
            results = []
            for p in papers[:max_results]:
                results.append({
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", [])[:5],
                    "abstract": (p.get("abstract", "") or "")[:500],
                    "published": str(p.get("published", "")),
                    "categories": p.get("categories", []),
                    "pdf_url": p.get("pdf_url", ""),
                })
            return {"papers": results, "total": len(results), "query": query}
    except Exception as e:
        logger.error("ArXiv search tool failed", exc_info=e)
        return {"error": f"ArXiv search failed: {str(e)}", "query": query}


async def _tool_ingest_arxiv(
    args: Dict[str, Any],
    user_id: str,
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Ingest arXiv papers into the RAG system by searching for them first, then ingesting."""
    from src.models.document import DocumentType, ProcessingStatus
    from src.services.arxiv.arxiv_service import ArXivIngestionService

    paper_ids = args.get("paper_ids", [])
    if not paper_ids:
        return {"error": "No paper IDs provided"}
    if len(paper_ids) > 10:
        return {"error": "Maximum 10 papers per ingest request"}

    try:
        async with ArXivIngestionService() as service:
            # Fetch paper metadata for each ID, then ingest
            papers_to_ingest = []
            for pid in paper_ids:
                # Search by ID to get full paper dict
                results = await service.search_papers(
                    query=f"id:{pid}",
                    max_results=1,
                )
                if results:
                    papers_to_ingest.append(results[0])
                else:
                    # Build minimal paper dict from ID
                    papers_to_ingest.append({
                        "id": pid,
                        "title": f"arXiv:{pid}",
                        "authors": [],
                        "abstract": "",
                        "published": "",
                        "updated": "",
                        "categories": [],
                        "links": {"pdf": f"https://arxiv.org/pdf/{pid}"},
                    })

            ingested = await service.ingest_papers(
                papers=papers_to_ingest,
                download_pdfs=True,
                extract_content=True,
            )

            document_ids = []
            if ingested and db and current_user:
                # Persist documents to the database so they get real UUIDs
                for doc in ingested:
                    document = Document(
                        title=getattr(doc, "title", "Untitled"),
                        filename=getattr(doc, "filename", ""),
                        file_path=getattr(
                            doc, "file_path",
                            getattr(doc, "filename", ""),
                        ),
                        file_size_bytes=getattr(doc, "file_size_bytes", 0),
                        mime_type=getattr(doc, "mime_type", "application/pdf"),
                        document_type=DocumentType.PDF,
                        content_text=getattr(doc, "content_text", None),
                        content_summary=getattr(doc, "content_summary", None),
                        document_metadata=_sanitize_metadata(getattr(doc, "document_metadata", {})),
                        processing_status=ProcessingStatus.COMPLETED,
                        uploaded_by_user_id=current_user.id,
                        organization_id=current_user.organization_id,
                        is_public=False,
                    )
                    db.add(document)
                    await db.flush()  # Generate UUID
                    document_ids.append(str(document.id))
                await db.commit()
            elif ingested:
                # Fallback: no db session, return paper_ids only
                for doc in ingested:
                    doc_id = getattr(doc, "id", None)
                    if doc_id:
                        document_ids.append(str(doc_id))

            return {
                "status": "ingestion_complete",
                "paper_ids": paper_ids,
                "document_ids": document_ids,
                "ingested_count": len(ingested) if ingested else len(papers_to_ingest),
                "message": f"Ingested {len(paper_ids)} paper(s) into the RAG system.",
            }
    except Exception as e:
        logger.error("ArXiv ingest tool failed", exc_info=e)
        if db:
            await db.rollback()
        return {"error": f"Ingestion failed: {str(e)}", "paper_ids": paper_ids}


async def _tool_search_documents(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Search user's indexed documents by title or filename."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    query = args.get("query", "")
    max_results = min(args.get("max_results", 10), 50)

    if not query:
        return {"error": "Query is required"}

    try:
        escaped = re.sub(r"([%_\\])", r"\\\1", query)
        pattern = f"%{escaped}%"
        stmt = (
            select(Document)
            .where(
                Document.organization_id == current_user.organization_id,
                Document.is_deleted == False,
                (Document.title.ilike(pattern) | Document.filename.ilike(pattern)),
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
                    "title": d.title,
                    "type": d.document_type.value if d.document_type else None,
                    "status": d.processing_status.value if d.processing_status else None,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in docs
            ],
            "total": len(docs),
            "query": query,
        }
    except Exception as e:
        logger.error("search_documents tool failed", exc_info=e)
        return {"error": f"Document search failed: {str(e)}"}


async def _resolve_document_id(
    document_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[Document]:
    """Resolve a document_id string (UUID or title) to a Document.

    Accepts either a UUID string or a document title. Returns None if not found.
    """
    # Try as UUID first
    try:
        doc_uuid = UUID(document_id)
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            return doc
    except (ValueError, AttributeError):
        pass

    # Try by title (case-insensitive)
    if document_id:
        try:
            stmt = (
                select(Document)
                .where(
                    Document.title.ilike(document_id),
                    Document.organization_id == current_user.organization_id,
                    Document.is_deleted == False,
                )
                .order_by(desc(Document.created_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                return doc
        except Exception:
            pass

    return None


async def _resolve_project_id(
    project_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[UUID]:
    """Resolve a project_id string to a UUID.

    Accepts either a UUID string or a project name. Returns None if not found.
    """
    # Try as UUID first
    try:
        return UUID(project_id)
    except (ValueError, AttributeError):
        pass

    # Try by name (case-insensitive)
    if project_id and db and current_user:
        try:
            stmt = (
                select(Collection.id)
                .join(Workspace, Collection.workspace_id == Workspace.id)
                .where(
                    Collection.name.ilike(project_id),
                    Collection.is_deleted == False,
                    Workspace.owner_id == current_user.id,
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return row
        except Exception:
            pass

    return None


async def _verify_project_ownership(
    project_id: str,
    db: AsyncSession,
    current_user: User,
) -> Optional[Collection]:
    """Verify a project (collection) exists and belongs to the current user."""
    proj_uuid = await _resolve_project_id(project_id, db, current_user)
    if not proj_uuid:
        return None

    stmt = (
        select(Collection)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            Collection.id == proj_uuid,
            Collection.is_deleted == False,
            Workspace.owner_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _tool_add_document_to_project(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Add an existing document to a research project.

    Uses a fresh DB session to avoid concurrency issues when the agent
    fires multiple add_document_to_project calls in parallel.
    """
    if not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    project_id = args.get("project_id", "")

    if not document_id:
        return {"error": "document_id is required"}
    if not project_id:
        return {"error": "project_id is required"}

    from src.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as fresh_db:
            # Resolve document (UUID or title)
            doc = await _resolve_document_id(document_id, fresh_db, current_user)
            if not doc:
                return {"error": "Document not found or access denied"}
            doc_uuid = doc.id

            # Verify project ownership (resolves UUID or name)
            project = await _verify_project_ownership(project_id, fresh_db, current_user)
            if not project:
                return {"error": "Project not found or access denied"}

            # Check if already linked
            existing_stmt = select(CollectionDocument).where(
                CollectionDocument.collection_id == project.id,
                CollectionDocument.document_id == doc_uuid,
            )
            existing_result = await fresh_db.execute(existing_stmt)
            if existing_result.scalar_one_or_none():
                return {
                    "status": "already_linked",
                    "message": f"Document '{doc.title}' is already in project '{project.name}'.",
                }

            link = CollectionDocument(
                collection_id=project.id,
                document_id=doc_uuid,
            )
            fresh_db.add(link)
            await fresh_db.commit()

            return {
                "status": "success",
                "message": f"Added document '{doc.title}' to project '{project.name}'.",
                "document_id": str(doc.id),
                "project_id": str(project.id),
            }
    except Exception as e:
        logger.error("add_document_to_project tool failed", exc_info=e)
        return {"error": f"Failed to add document to project: {str(e)}"}


async def _tool_create_project_note(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Create a markdown note in a research project."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    project_id = args.get("project_id", "")
    title = args.get("title", "")
    content = args.get("content", "")
    tags = args.get("tags", [])

    if not title:
        return {"error": "title is required"}
    if not content:
        return {"error": "content is required"}
    if not project_id:
        return {"error": "project_id is required"}

    try:
        # Verify project ownership (resolves UUID or name)
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        # Use savepoint so this commit survives later rollbacks
        async with db.begin_nested():
            note = ProjectNote(
                project_id=project.id,
                user_id=current_user.id,
                title=title,
                content=content,
                tags=tags or [],
            )
            db.add(note)
        await db.commit()

        return {
            "status": "success",
            "note_id": str(note.id),
            "title": note.title,
            "project_name": project.name,
            "message": f"Created note '{title}' in project '{project.name}'.",
        }
    except Exception as e:
        logger.error("create_project_note tool failed", exc_info=e)
        try:
            await db.rollback()
        except Exception:
            pass
        return {"error": f"Failed to create note: {str(e)}"}


async def _tool_list_project_documents(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """List all documents in a research project."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    project_id = args.get("project_id", "")
    if not project_id:
        return {"error": "project_id is required"}

    try:
        # Verify project ownership (resolves UUID or name)
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        stmt = (
            select(Document)
            .join(CollectionDocument, CollectionDocument.document_id == Document.id)
            .where(
                CollectionDocument.collection_id == project.id,
                Document.is_deleted == False,
            )
            .order_by(desc(Document.created_at))
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()

        return {
            "project_name": project.name,
            "documents": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "type": d.document_type.value if d.document_type else None,
                    "status": d.processing_status.value if d.processing_status else None,
                }
                for d in docs
            ],
            "total": len(docs),
        }
    except Exception as e:
        logger.error("list_project_documents tool failed", exc_info=e)
        return {"error": f"Failed to list project documents: {str(e)}"}


async def _tool_summarize_document(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Summarize a document using text extraction + LLM."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    if not document_id:
        return {"error": "document_id is required"}

    try:
        doc = await _resolve_document_id(document_id, db, current_user)
        if not doc:
            return {"error": "Document not found or access denied"}

        # Use existing content_text if available, else extract
        text = doc.content_text or ""
        if not text:
            from src.services.documents.file_service import FileService

            file_service = FileService(db)
            text = file_service.extract_text_content(doc)

        if not text or text.startswith("Error"):
            return {"error": "Could not extract text from document"}

        # Truncate for LLM context
        text_for_summary = text[:8000]
        word_count = len(text.split())

        # Use LLM to summarize
        try:
            from src.services.agent.graph import _build_llm

            llm = _build_llm()
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await llm.ainvoke([
                SystemMessage(content="You are a research assistant. Provide a concise summary of the following document in 3-5 paragraphs. Focus on key findings, methodology, and conclusions."),
                HumanMessage(content=text_for_summary),
            ])
            summary = response.content
        except Exception:
            # Fallback: first 500 words
            words = text.split()
            summary = " ".join(words[:500]) + ("..." if len(words) > 500 else "")

        return {
            "summary": summary,
            "word_count": word_count,
            "title": doc.title or "Untitled",
            "document_id": str(doc.id),
        }
    except Exception as e:
        logger.error("summarize_document tool failed", exc_info=e)
        return {"error": f"Summarization failed: {str(e)}"}


async def _tool_compare_documents(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Compare multiple documents using text extraction + LLM."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_ids = args.get("document_ids", [])
    comparison_type = args.get("type", "general")
    if not document_ids or len(document_ids) < 2:
        return {"error": "At least 2 document_ids are required"}
    if len(document_ids) > 5:
        return {"error": "Maximum 5 documents can be compared at once"}

    try:
        from src.services.documents.file_service import FileService

        file_service = FileService(db)
        doc_texts = []

        for did in document_ids:
            doc = await _resolve_document_id(did, db, current_user)
            if not doc:
                return {"error": f"Document not found: {did}"}

            text = doc.content_text or ""
            if not text:
                text = file_service.extract_text_content(doc)

            doc_texts.append({
                "id": str(doc.id),
                "title": doc.title or "Untitled",
                "text": text[:4000],
            })

        # Use LLM to compare
        try:
            from src.services.agent.graph import _build_llm

            llm = _build_llm()
            from langchain_core.messages import HumanMessage, SystemMessage

            docs_content = "\n\n---\n\n".join(
                f"Document: {d['title']}\n{d['text']}" for d in doc_texts
            )
            response = await llm.ainvoke([
                SystemMessage(content=f"You are a research assistant. Compare the following documents ({comparison_type} comparison). Identify similarities, differences, and key themes across them. Be structured and concise."),
                HumanMessage(content=docs_content),
            ])
            comparison = response.content
        except Exception:
            comparison = "Comparison could not be generated. Documents were retrieved successfully."

        return {
            "comparison": comparison,
            "count": len(doc_texts),
            "documents": [{"id": d["id"], "title": d["title"]} for d in doc_texts],
            "type": comparison_type,
        }
    except Exception as e:
        logger.error("compare_documents tool failed", exc_info=e)
        return {"error": f"Comparison failed: {str(e)}"}


async def _tool_extract_entities(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Extract named entities from a document."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    if not document_id:
        return {"error": "document_id is required"}

    try:
        doc = await _resolve_document_id(document_id, db, current_user)
        if not doc:
            return {"error": "Document not found or access denied"}

        text = doc.content_text or ""
        if not text:
            from src.services.documents.file_service import FileService

            file_service = FileService(db)
            text = file_service.extract_text_content(doc)

        if not text or text.startswith("Error"):
            return {"error": "Could not extract text from document"}

        # Truncate for entity extraction
        text_for_extraction = text[:10000]

        from src.services.documents.enhanced_document_processing_service import EntityExtractor

        extractor = EntityExtractor()
        result = await extractor.extract_entities(text_for_extraction, str(doc.id))

        if result.success and result.data:
            entities = result.data.get("entities", [])
            return {
                "entities": [
                    {
                        "text": e.get("text", ""),
                        "type": e.get("label", "UNKNOWN"),
                        "confidence": e.get("confidence", 0.0),
                    }
                    for e in entities[:50]
                ],
                "total": len(entities),
                "document_id": document_id,
                "title": doc.title or "Untitled",
            }
        return {"entities": [], "total": 0, "document_id": document_id}
    except Exception as e:
        logger.error("extract_entities tool failed", exc_info=e)
        return {"error": f"Entity extraction failed: {str(e)}"}


async def _tool_search_knowledge_graph(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search the knowledge graph for entities."""
    query = args.get("query", "")
    entity_types = args.get("entity_types")
    limit = min(args.get("limit", 20), 50)

    if not query:
        return {"error": "query is required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import KnowledgeGraphService
        from src.models.graph import EntityType

        kg_service = KnowledgeGraphService()

        type_filters = None
        if entity_types:
            type_filters = []
            for et in entity_types:
                try:
                    type_filters.append(EntityType(et.upper()))
                except ValueError:
                    pass

        entities = kg_service.search_entities(
            query=query,
            entity_types=type_filters,
            limit=limit,
        )

        return {
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type.value if e.entity_type else "UNKNOWN",
                    "confidence": e.confidence_score,
                }
                for e in entities
            ],
            "total": len(entities),
            "query": query,
        }
    except Exception as e:
        logger.error("search_knowledge_graph tool failed", exc_info=e)
        return {"error": f"Knowledge graph search failed: {str(e)}"}


async def _tool_create_draft(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Create a literature review draft for a project."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    project_id = args.get("project_id", "")
    themes = args.get("themes", [])
    style = args.get("style", "academic")

    if not project_id:
        return {"error": "project_id is required"}
    if not themes:
        return {"error": "At least one theme is required"}

    try:
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        from src.core.database import AsyncSessionLocal
        from src.services.research.draft_generation_service import DraftGenerationService

        # Use a fresh independent session for draft generation — the agent's
        # session may be rolled back before the async background task completes.
        draft_db = AsyncSessionLocal()
        draft_service = DraftGenerationService(draft_db)
        result = await draft_service.generate_draft(
            project_id=project.id,
            user_id=current_user.id,
            themes=themes,
            style=style,
        )

        return {
            "task_id": result.get("task_id", ""),
            "status": str(result.get("status", "pending")),
            "message": f"Draft generation started for project '{project.name}'. It will appear in the Drafts tab once complete.",
            "project_id": str(project.id),
            "project_name": project.name,
        }
    except Exception as e:
        logger.error("create_draft tool failed", exc_info=e)
        return {"error": f"Draft creation failed: {str(e)}"}


async def _tool_export_bibliography(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Export bibliography for given documents."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_ids = args.get("document_ids", [])
    bib_format = args.get("format", "bibtex").lower()

    if not document_ids:
        return {"error": "At least one document_id is required"}
    if bib_format not in ("bibtex", "apa", "ieee", "mla"):
        return {"error": f"Unsupported format: {bib_format}. Use bibtex, apa, ieee, or mla."}

    try:
        # Fetch citations for the given documents
        citations = []
        for did in document_ids:
            try:
                doc_uuid = UUID(did)
            except (ValueError, AttributeError):
                continue

            stmt = (
                select(Citation)
                .where(Citation.document_id == doc_uuid)
            )
            result = await db.execute(stmt)
            doc_citations = result.scalars().all()
            citations.extend(doc_citations)

        if not citations:
            return {
                "bibliography": "",
                "format": bib_format,
                "count": 0,
                "message": "No citations found for the given documents.",
            }

        from src.services.research.bibliography_service import BibliographyService

        bibliography = BibliographyService.format_bibliography(citations, bib_format)

        return {
            "bibliography": bibliography,
            "format": bib_format,
            "count": len(citations),
        }
    except Exception as e:
        logger.error("export_bibliography tool failed", exc_info=e)
        return {"error": f"Bibliography export failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAGE_TYPES = {"project", "documents", "dashboard", "chat", "unknown"}


def build_agent_system_prompt(page_context: PageContextRequest) -> str:
    ctx_type = page_context.type if page_context.type in VALID_PAGE_TYPES else "unknown"
    context_line = ""
    if ctx_type == "project" and page_context.project_id:
        context_line = f"The user is viewing a project (ID: {page_context.project_id})."
    elif ctx_type != "unknown":
        context_line = f"The user is on the {ctx_type} page."

    return f"""You are an AI research agent for a RAG-powered academic research system.
You help users search documents, manage research projects, find ArXiv papers, create notes, and analyze research.

You have access to the following tools:
- **search_arxiv**: Search arXiv for academic papers. Use when the user asks to find research papers or scientific articles.
- **ingest_arxiv_papers**: Ingest arXiv papers into the RAG system. Use when the user wants to add/import specific arXiv papers by ID.
- **search_documents**: Search the user's indexed documents by title or content. Use when the user wants to find documents they have already uploaded.
- **add_document_to_project**: Add an existing document to a research project. Use when the user wants to organize a document into a project.
- **create_project_note**: Create a markdown note in a research project. Use when the user wants to write or save notes, observations, or summaries.
- **list_project_documents**: List all documents in a research project. Use when the user wants to see what documents are in a project.
- **summarize_document**: Summarize a document's content. Use for overviews or summaries of specific documents.
- **compare_documents**: Compare 2-5 documents for similarities, differences, and themes.
- **extract_entities**: Extract named entities (people, organizations, concepts) from a document.
- **search_knowledge_graph**: Search the knowledge graph for entities and their relationships.
- **create_draft**: Generate a literature review draft from project documents around specific themes.
- **export_bibliography**: Export bibliography for documents in bibtex, apa, ieee, or mla format.

{context_line}
When the user is on a project page, the project_id is available from the page context and does not need to be asked for.

When answering questions, use retrieved document context when available.
Cite sources using [Doc N] format inline.
Be concise and action-oriented."""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

AGENT_THREAD_MARKER = {"source": "agent"}


async def _persist_thread_messages(
    db: AsyncSession,
    current_user: User,
    request: AgentExecuteRequest,
    assistant_content: str,
    tool_executions_out: Optional[List[ToolExecutionResponse]] = None,
) -> tuple[str, str]:
    """Persist thread & messages to the database.

    Returns ``(thread_id, conversation_id)`` as strings.
    """
    thread_id = request.thread_id or ""
    conversation_id = ""

    # Resolve or create thread
    thread: Optional[Thread] = None
    if request.thread_id:
        thread = await db.get(Thread, UUID(request.thread_id))

    if thread is None:
        # Need a workspace + conversation for the thread
        ws_stmt = select(Workspace).where(
            Workspace.owner_id == current_user.id
        ).limit(1)
        ws_result = await db.execute(ws_stmt)
        workspace = ws_result.scalar_one_or_none()

        if workspace:
            # Create conversation
            conv = Conversation(
                workspace_id=workspace.id,
                title="Agent Chat",
                created_by_id=current_user.id,
            )
            db.add(conv)
            await db.flush()

            # Derive title from first user message
            first_msg = next(
                (m.content for m in request.messages if m.role == "user"), ""
            )
            title = first_msg[:80] if first_msg else "Agent Chat"

            thread = Thread(
                conversation_id=conv.id,
                title=title,
                status=ThreadStatus.ACTIVE,
                created_by_id=current_user.id,
                rag_document_scope=AGENT_THREAD_MARKER,
                message_count=0,
            )
            db.add(thread)
            await db.flush()

    if thread:
        thread_id = str(thread.id)
        conversation_id = str(thread.conversation_id)

        # Save user message (only the latest one)
        last_user_content = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            None,
        )
        if last_user_content:
            user_msg = ChatMessage(
                thread_id=thread.id,
                user_id=current_user.id,
                role=MessageRole.USER,
                content=last_user_content,
            )
            db.add(user_msg)

        # Save assistant message with tool executions
        tool_exec_data = None
        if tool_executions_out:
            tool_exec_data = [
                {
                    "id": te.id,
                    "tool_name": te.tool_name,
                    "tool_display_name": te.tool_display_name,
                    "args": te.args,
                    "status": te.status,
                    "result": te.result,
                    "error": te.error,
                    "duration_ms": te.duration_ms,
                }
                for te in tool_executions_out
            ]
        asst_msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            model_name=request.model,
            tool_executions=tool_exec_data,
        )
        db.add(asst_msg)

        # Update thread stats
        thread.message_count = (thread.message_count or 0) + 2
        thread.last_message_at = datetime.now(timezone.utc)

        await db.commit()

    return thread_id, conversation_id


# ---------------------------------------------------------------------------
# Background graph runner
# ---------------------------------------------------------------------------


async def _run_agent_graph(
    job_id: str,
    request: AgentExecuteRequest,
    current_user: User,
    db: AsyncSession,
):
    """Run the LangGraph agent graph in the background and update job status."""
    from langchain_core.messages import HumanMessage

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    try:
        # Configure LangSmith tracing if available
        try:
            from src.services.agent.observability import configure_langsmith

            configure_langsmith()
        except Exception:
            pass

        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        messages = [
            HumanMessage(content=m.content)
            for m in request.messages
            if m.role == "user"
        ]

        initial_state = {
            "messages": messages,
            "page_context": {
                "type": request.page_context.type,
                "project_id": request.page_context.project_id,
                "project_name": request.page_context.project_name,
                "label": request.page_context.label,
                "metadata": request.page_context.metadata,
            },
            "retrieved_contexts": [],
            "tool_executions": [],
            "thread_id": request.thread_id or "",
            "tool_loop_count": 0,
            "error_count": 0,
            "last_error": "",
            "pending_confirmation": {},
            "user_confirmed": False,
            "intent": "",
            "user_memories": [],
        }

        config = {
            "configurable": {
                "thread_id": request.thread_id or job_id,
                "db": db,
                "current_user": current_user,
                "page_context": {
                    "type": request.page_context.type,
                    "project_id": request.page_context.project_id,
                    "project_name": request.page_context.project_name,
                    "label": request.page_context.label,
                    "metadata": request.page_context.metadata,
                },
            }
        }

        try:
            final_state = await graph.ainvoke(initial_state, config=config)
        except GraphInterrupt as exc:
            interrupts = getattr(exc, "interrupts", [])
            confirmation_details = {}
            if interrupts:
                confirmation_details = getattr(interrupts[0], "value", {})
            _set_job(job_id, {
                "status": "awaiting_confirmation",
                "confirmation": confirmation_details,
                "tool_executions": [],
                "user_id": str(current_user.id),
                "request": request.model_dump(),
            })
            return

        # Extract assistant content from the last AI message
        assistant_content = ""
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist thread & messages
        thread_id, conversation_id = "", ""
        try:
            tool_executions_out = [
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None
            thread_id, conversation_id = await _persist_thread_messages(
                db, current_user, request, assistant_content, tool_executions_out,
            )
        except Exception as e:
            logger.warning("Failed to persist thread", exc_info=e)
            # Only rollback the thread persistence, not tool side-effects
            # The session may already be in an invalid state, so be cautious
            try:
                await db.rollback()
            except Exception:
                pass
            # Start a fresh transaction for any subsequent operations
            try:
                await db.begin()
            except Exception:
                pass

        # Build response
        result = AgentExecuteResponse(
            message=AgentMessage(role="assistant", content=assistant_content),
            model="gpt-4o",
            usage={},
            finish_reason="stop",
            timestamp=datetime.now(timezone.utc).isoformat(),
            rag_enabled=request.use_rag,
            retrieved_contexts=[
                RetrievedContextResponse(**rc)
                for rc in final_state.get("retrieved_contexts", [])
            ] or None,
            tool_executions=[
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )

        _set_job(job_id, {
            "status": "completed",
            "result": result.model_dump(),
            "tool_executions": [
                te for te in final_state.get("tool_executions", [])
            ],
        })
    except Exception as e:
        logger.error("Agent graph execution failed", exc_info=e)
        _set_job(job_id, {"status": "failed", "error": str(e)})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/execute", response_model=JobStartResponse)
async def execute_agent(
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an agent chat completion via LangGraph.

    Returns a job ID immediately.  Poll ``GET /jobs/{job_id}`` for the result.
    """
    logger.info(
        "Agent execute request",
        extra={
            "user_id": str(current_user.id),
            "page_context": request.page_context.type,
            "message_count": len(request.messages),
            "use_rag": request.use_rag,
        },
    )

    job_id = str(_uuid.uuid4())
    _set_job(job_id, {"status": "running", "tool_executions": [], "user_id": str(current_user.id), "request": request.model_dump()})

    background_tasks.add_task(
        _run_agent_graph, job_id, request, current_user, db,
    )
    return JobStartResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """Poll for agent job status."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


class ConfirmationRequest(BaseModel):
    confirmed: bool = Field(..., description="Whether the user confirms the action")


@router.post("/confirm/{job_id}")
async def confirm_agent_action(
    job_id: str,
    request: ConfirmationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm or deny a pending agent action (human-in-the-loop)."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="Job is not awaiting confirmation")

    # Resume the graph with the user's decision
    background_tasks.add_task(
        _resume_agent_graph, job_id, request.confirmed, current_user, db,
    )
    _set_job(job_id, {**job, "status": "running"})
    return {"status": "running", "job_id": job_id}


async def _resume_agent_graph(
    job_id: str,
    confirmed: bool,
    current_user: User,
    db: AsyncSession,
):
    """Resume the agent graph after human confirmation."""
    from langgraph.types import Command

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    try:
        checkpointer = await get_checkpointer()
        graph = compile_agent_graph(checkpointer=checkpointer)

        config = {
            "configurable": {
                "thread_id": job_id,
                "db": db,
                "current_user": current_user,
            }
        }

        final_state = await graph.ainvoke(
            Command(resume={"confirmed": confirmed}),
            config=config,
        )

        # Extract assistant content
        assistant_content = ""
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                assistant_content = msg.content
                break

        # Persist thread messages
        try:
            job = _get_job(job_id)
            if job and job.get("request"):
                original_request = AgentExecuteRequest(**job["request"])
                tool_executions_out = [
                    ToolExecutionResponse(**te)
                    for te in final_state.get("tool_executions", [])
                ] or None
                await _persist_thread_messages(
                    db, current_user, original_request, assistant_content, tool_executions_out,
                )
        except Exception as e:
            logger.warning("Failed to persist confirmation thread messages", exc_info=e)

        result = AgentExecuteResponse(
            message=AgentMessage(role="assistant", content=assistant_content),
            model="gpt-4o",
            usage={},
            finish_reason="stop",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool_executions=[
                ToolExecutionResponse(**te)
                for te in final_state.get("tool_executions", [])
            ] or None,
        )

        _set_job(job_id, {
            "status": "completed",
            "result": result.model_dump(),
            "tool_executions": final_state.get("tool_executions", []),
        })
    except Exception as e:
        logger.error("Agent graph resume failed", exc_info=e)
        _set_job(job_id, {"status": "failed", "error": str(e)})


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/stream")
async def stream_agent(
    request_body: AgentExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream agent responses via Server-Sent Events.

    SSE event types: token, tool_start, tool_end, rag_context, done, error
    """
    from langchain_core.messages import HumanMessage

    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph

    async def event_generator():
        import json as _json

        try:
            checkpointer = await get_checkpointer()
            graph = compile_agent_graph(checkpointer=checkpointer)

            messages = [
                HumanMessage(content=m.content)
                for m in request_body.messages
                if m.role == "user"
            ]

            initial_state = {
                "messages": messages,
                "page_context": {
                    "type": request_body.page_context.type,
                    "project_id": request_body.page_context.project_id,
                },
                "retrieved_contexts": [],
                "tool_executions": [],
                "thread_id": request_body.thread_id or "",
                "tool_loop_count": 0,
                "error_count": 0,
                "last_error": "",
                "pending_confirmation": {},
                "user_confirmed": False,
                "intent": "",
                "user_memories": [],
            }

            config = {
                "configurable": {
                    "thread_id": request_body.thread_id or str(_uuid.uuid4()),
                    "db": db,
                    "current_user": current_user,
                    "page_context": {
                        "type": request_body.page_context.type,
                        "project_id": request_body.page_context.project_id,
                    },
                }
            }

            async with asyncio.timeout(300):  # 5 minutes
                async for event in graph.astream_events(
                    initial_state, config=config, version="v2"
                ):
                    if await request.is_disconnected():
                        break

                    kind = event.get("event", "")
                    name = event.get("name", "")

                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield f"event: token\ndata: {_json.dumps({'content': chunk.content})}\n\n"

                    elif kind == "on_tool_start":
                        yield f"event: tool_start\ndata: {_json.dumps({'tool': name})}\n\n"

                    elif kind == "on_tool_end":
                        output = event.get("data", {}).get("output", "")
                        yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': str(output)[:500]})}\n\n"

                    elif kind == "on_chain_end" and name == "rag_node":
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict):
                            contexts = output.get("retrieved_contexts", [])
                            if contexts:
                                yield f"event: rag_context\ndata: {_json.dumps({'contexts': contexts[:3]})}\n\n"

            # Persist messages after streaming completes
            try:
                final_snapshot = await graph.aget_state(config)
                final_values = final_snapshot.values if final_snapshot else {}

                assistant_content = ""
                for msg in reversed(final_values.get("messages", [])):
                    if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                        assistant_content = msg.content
                        break

                tool_executions_out = [
                    ToolExecutionResponse(**te)
                    for te in final_values.get("tool_executions", [])
                ] or None

                await _persist_thread_messages(
                    db, current_user, request_body, assistant_content, tool_executions_out,
                )
            except Exception as e:
                logger.warning("Failed to persist SSE thread messages", exc_info=e)

            yield f"event: done\ndata: {_json.dumps({'status': 'complete'})}\n\n"

        except Exception as e:
            logger.error("SSE stream error", exc_info=e)
            yield f"event: error\ndata: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/graph/mermaid")
async def get_graph_mermaid(
    current_user: User = Depends(get_current_user),
):
    """Get the agent graph structure as a Mermaid diagram. Admin-only."""
    from src.services.agent.visualization import get_graph_mermaid

    diagram = get_graph_mermaid()
    return {"mermaid": diagram}


@router.get("/graph/trace/{thread_id}")
async def get_graph_trace(
    thread_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get an execution trace for a thread as a Mermaid sequence diagram."""
    from src.services.agent.visualization import get_execution_trace_mermaid

    diagram = await get_execution_trace_mermaid(thread_id)
    if diagram is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"mermaid": diagram, "thread_id": thread_id}


@router.get("/health")
async def agent_health():
    """Health check for agent service."""
    return {"status": "ok", "service": "agent"}


# ---------------------------------------------------------------------------
# Thread listing & message retrieval schemas
# ---------------------------------------------------------------------------

class ThreadSummary(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int
    last_message_at: Optional[str] = None
    source_project_id: Optional[str] = None
    status: str = "active"
    conversation_id: str = ""


class ThreadListResponse(BaseModel):
    threads: List[ThreadSummary]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    tool_executions: Optional[List[Dict[str, Any]]] = None


class ThreadMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int


# ---------------------------------------------------------------------------
# Thread listing & message retrieval endpoints
# ---------------------------------------------------------------------------

@router.get("/threads", response_model=ThreadListResponse)
async def list_agent_threads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List threads for the current user, ordered by most recently updated."""
    # Build query: Thread -> Conversation -> Workspace, filter by owner
    stmt = (
        select(Thread)
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
            Thread.rag_document_scope == AGENT_THREAD_MARKER,
        )
        .order_by(desc(Thread.updated_at))
        .limit(50)
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()

    # Count total (without limit)
    count_stmt = (
        select(func.count(Thread.id))
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
            Thread.rag_document_scope == AGENT_THREAD_MARKER,
        )
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    thread_summaries = []
    for t in threads:
        thread_summaries.append(
            ThreadSummary(
                id=str(t.id),
                title=t.title,
                created_at=t.created_at.isoformat() if t.created_at else "",
                updated_at=t.updated_at.isoformat() if t.updated_at else "",
                message_count=t.message_count or 0,
                last_message_at=t.last_message_at.isoformat() if t.last_message_at else None,
                source_project_id=str(t.source_project_id) if t.source_project_id else None,
                status=t.status.value if t.status else "active",
                conversation_id=str(t.conversation_id) if t.conversation_id else "",
            )
        )

    return ThreadListResponse(threads=thread_summaries, total=total)


@router.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific agent thread, verifying user ownership."""
    # Verify thread exists and belongs to the current user via ownership chain
    ownership_stmt = (
        select(Thread)
        .join(Conversation, Thread.conversation_id == Conversation.id)
        .join(Workspace, Conversation.workspace_id == Workspace.id)
        .where(
            Thread.id == thread_id,
            Workspace.owner_id == current_user.id,
            Thread.is_deleted == False,
        )
    )
    ownership_result = await db.execute(ownership_stmt)
    thread = ownership_result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Fetch messages with citations eagerly loaded
    messages_stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .options(selectinload(ChatMessage.citations))
        .order_by(ChatMessage.created_at.asc())
    )
    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    message_responses = []
    for msg in messages:
        # Build citations list from the relationship
        citations_data = None
        if msg.citations:
            citations_data = [c.to_frontend_format() for c in msg.citations]

        message_responses.append(
            MessageResponse(
                id=str(msg.id),
                role=msg.role.value if msg.role else "user",
                content=msg.content or "",
                created_at=msg.created_at.isoformat() if msg.created_at else "",
                tool_name=msg.tool_name,
                tool_call_id=msg.tool_call_id,
                citations=citations_data,
                tool_executions=msg.tool_executions,
            )
        )

    return ThreadMessagesResponse(messages=message_responses, total=len(message_responses))
