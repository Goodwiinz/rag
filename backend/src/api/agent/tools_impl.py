"""Agent tool implementations.

Contains all _tool_* functions and the execute_tool dispatcher.
Each function performs a specific action (search, ingest, summarize, etc.)
and returns a dict result.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.collection import CollectionDocument
from src.models.document import Document
from src.models.project_note import ProjectNote
from src.models.user import User

from .tool_helpers import (
    _resolve_document_id,
    _sanitize_metadata,
    _verify_project_ownership,
)

logger = logging.getLogger(__name__)


def _escape_like(value: str) -> str:
    """Escape special LIKE pattern characters for safe ilike() queries."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# AGENT_TOOLS definition (tool schemas for OpenAI function calling)
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
            "description": "Add an ALREADY-INGESTED document to a research project. The document must exist in the system first — use ingest_arxiv_papers to ingest papers before calling this. Will fail if the document UUID does not exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to add. Must be a valid UUID from a prior ingest or search_documents result — NOT an arXiv paper ID.",
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
            "name": "explore_entity_neighborhood",
            "description": "Explore an entity's neighborhood in the knowledge graph — find connected entities and the relationships between them. Use when the user asks 'what is connected to X', 'show me everything related to X', or wants to understand how an entity fits in the broader knowledge graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "UUID of the entity to explore. Get this from search_knowledge_graph results.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "How many hops to traverse (1-3). Default 2.",
                        "default": 2,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of connected entities to return. Default 30.",
                        "default": 30,
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_entity_paths",
            "description": "Find relationship paths between two entities in the knowledge graph. Use when the user asks 'how is X related to Y', 'what connects X and Y', or wants to understand the chain of relationships between two concepts/people/organizations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_entity_id": {
                        "type": "string",
                        "description": "UUID of the starting entity. Get this from search_knowledge_graph results.",
                    },
                    "target_entity_id": {
                        "type": "string",
                        "description": "UUID of the destination entity. Get this from search_knowledge_graph results.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum path length (1-5). Default 3.",
                        "default": 3,
                    },
                },
                "required": ["source_entity_id", "target_entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_graph_stats",
            "description": "Get statistics about the knowledge graph — total entities, relationships, type distributions, and connectivity metrics. Use when the user asks about the size or shape of the knowledge base, wants an overview of what's in the graph, or asks 'how many entities/relationships do we have'.",
            "parameters": {
                "type": "object",
                "properties": {},
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


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


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
    if tool_name == "explore_entity_neighborhood":
        return await _tool_explore_entity_neighborhood(args)
    if tool_name == "find_entity_paths":
        return await _tool_find_entity_paths(args)
    if tool_name == "get_graph_stats":
        return await _tool_get_graph_stats(args)
    if tool_name == "create_draft":
        return await _tool_create_draft(args, db, current_user)
    if tool_name == "export_bibliography":
        return await _tool_export_bibliography(args, db, current_user)
    if tool_name == "execute_code":
        return await _tool_execute_code(args, thread_id="", current_user=current_user)
    return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


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
            if ingested and current_user:
                # Use a fresh DB session to avoid concurrency issues with the
                # shared graph session (same pattern as _tool_add_document_to_project).
                from src.core.database import AsyncSessionLocal

                try:
                    async with AsyncSessionLocal() as fresh_db:
                        async with fresh_db.begin():
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
                                fresh_db.add(document)
                                await fresh_db.flush()
                                document_ids.append(str(document.id))
                            # begin() auto-commits on exit
                    logger.info("Ingested %d documents to DB: %s", len(document_ids), document_ids)
                except Exception as db_err:
                    logger.error("Failed to persist ingested documents to DB", exc_info=db_err)
                    document_ids = []
                    return {"error": f"Papers downloaded but DB persist failed: {str(db_err)}"}
            elif ingested:
                # Fallback: no current_user, return paper_ids only
                for doc in ingested:
                    doc_id = getattr(doc, "id", None)
                    if doc_id:
                        document_ids.append(str(doc_id))

            return {
                "status": "ingestion_complete",
                "paper_ids": paper_ids,
                "document_ids": document_ids,
                "ingested_count": len(document_ids),
                "message": f"Ingested {len(document_ids)} paper(s) into the RAG system.",
            }
    except Exception as e:
        logger.error("ArXiv ingest tool failed", exc_info=e)
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
        pattern = f"%{_escape_like(query)}%"
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
                return {
                    "error": f"Document '{document_id}' not found. The document must be ingested into the system first. "
                    "Use ingest_arxiv_papers to ingest papers, then use the returned document_ids (UUIDs)."
                }
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

    from src.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as fresh_db:
            # Verify project ownership (resolves UUID or name)
            project = await _verify_project_ownership(project_id, fresh_db, current_user)
            if not project:
                return {"error": "Project not found or access denied"}

            note = ProjectNote(
                project_id=project.id,
                user_id=current_user.id,
                title=title,
                content=content,
                tags=tags or [],
            )
            fresh_db.add(note)
            await fresh_db.commit()

            return {
                "status": "success",
                "note_id": str(note.id),
                "title": note.title,
                "project_name": project.name,
                "message": f"Created note '{title}' in project '{project.name}'.",
            }
    except Exception as e:
        logger.error("create_project_note tool failed", exc_info=e)
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


async def _tool_explore_entity_neighborhood(args: Dict[str, Any]) -> Dict[str, Any]:
    """Explore an entity's neighborhood — connected entities and relationships."""
    entity_id = args.get("entity_id", "")
    max_depth = min(args.get("max_depth", 2), 3)
    limit = min(args.get("limit", 30), 50)

    if not entity_id:
        return {"error": "entity_id is required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service

        neighborhood = knowledge_graph_service.get_neighborhood(
            entity_id=entity_id,
            max_depth=max_depth,
            limit=limit,
        )

        entities = neighborhood.get("entities", [])
        relationships = neighborhood.get("relationships", [])

        return {
            "center_entity_id": entity_id,
            "connected_entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type.value if e.entity_type else "UNKNOWN",
                    "confidence": e.confidence_score,
                }
                for e in entities
            ],
            "relationships": [
                {
                    "source": r.source_entity_id,
                    "target": r.target_entity_id,
                    "type": r.relationship_type.value if r.relationship_type else "RELATED_TO",
                    "strength": r.strength,
                }
                for r in relationships
            ],
            "total_entities": len(entities),
            "total_relationships": len(relationships),
        }
    except Exception as e:
        logger.error("explore_entity_neighborhood tool failed", exc_info=e)
        return {"error": f"Neighborhood exploration failed: {str(e)}"}


async def _tool_find_entity_paths(args: Dict[str, Any]) -> Dict[str, Any]:
    """Find relationship paths between two entities."""
    source_id = args.get("source_entity_id", "")
    target_id = args.get("target_entity_id", "")
    max_depth = min(args.get("max_depth", 3), 5)

    if not source_id or not target_id:
        return {"error": "source_entity_id and target_entity_id are required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service

        paths = knowledge_graph_service.find_paths(
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth,
        )

        return {
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "paths_found": len(paths),
            "paths": [
                {
                    "length": p.path_length,
                    "strength": p.total_strength,
                    "confidence": p.confidence_score,
                    "entities": [
                        {"id": e.id, "name": e.name, "type": e.entity_type.value if e.entity_type else "UNKNOWN"}
                        for e in p.entities
                    ],
                    "relationships": [
                        {
                            "source": r.source_entity_id,
                            "target": r.target_entity_id,
                            "type": r.relationship_type.value if r.relationship_type else "RELATED_TO",
                        }
                        for r in p.relationships
                    ],
                }
                for p in paths[:5]  # Cap at 5 paths to keep response manageable
            ],
        }
    except Exception as e:
        logger.error("find_entity_paths tool failed", exc_info=e)
        return {"error": f"Path finding failed: {str(e)}"}


async def _tool_get_graph_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get knowledge graph statistics."""
    try:
        from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service

        analytics = knowledge_graph_service.get_graph_analytics()

        return {
            "total_entities": analytics.total_entities,
            "total_relationships": analytics.total_relationships,
            "entity_type_distribution": analytics.entity_type_counts,
            "relationship_type_distribution": analytics.relationship_type_counts,
            "average_degree": round(analytics.average_degree, 2),
            "connected_components": analytics.connected_components,
        }
    except Exception as e:
        logger.error("get_graph_stats tool failed", exc_info=e)
        return {"error": f"Graph stats retrieval failed: {str(e)}"}


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
        async with AsyncSessionLocal() as draft_db:
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

            # Verify document belongs to user's organization before fetching citations
            doc_stmt = select(Document).where(
                Document.id == doc_uuid,
                Document.organization_id == current_user.organization_id,
                Document.is_deleted == False,
            )
            doc_result = await db.execute(doc_stmt)
            if not doc_result.scalar_one_or_none():
                continue  # skip documents user doesn't have access to

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
# Code Execution Tool
# ---------------------------------------------------------------------------


async def _tool_execute_code(
    args: Dict[str, Any],
    thread_id: str = "",
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Execute code in an E2B sandbox."""
    if not current_user:
        return {"error": "Authentication required"}

    code = args.get("code", "")
    description = args.get("description", "")
    language = args.get("language", "python")
    packages = args.get("packages")

    if not code:
        return {"error": "No code provided"}

    from src.services.sandbox.e2b_sandbox_manager import get_sandbox_manager

    manager = get_sandbox_manager()

    if not manager.is_available:
        return {
            "error": "Code execution is not available. E2B_API_KEY not configured."
        }

    # Install extra packages if requested
    if packages:
        install_result = await manager.install_packages(thread_id, packages)
        if install_result.error:
            logger.warning(f"Package install warning: {install_result.stderr}")

    result = await manager.execute(
        thread_id=thread_id,
        code=code,
        language=language,
    )

    response: Dict[str, Any] = {
        "status": "success" if result.exit_code == 0 else "error",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "execution_time_ms": result.execution_time_ms,
        "description": description,
    }

    if result.error:
        response["error"] = result.error

    if result.results:
        response["outputs"] = result.results

    return response
