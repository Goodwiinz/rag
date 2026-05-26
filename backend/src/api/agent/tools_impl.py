"""Agent tool implementations.

Contains all _tool_* functions and the execute_tool dispatcher.
Each function performs a specific action (search, ingest, summarize, etc.)
and returns a dict result.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

# Matches the trailing ``vN`` revision suffix arXiv appends to paper IDs
# (e.g. ``2605.10877v1``). Used to compare requested vs. ingested IDs
# without false negatives across version bumps.
_ARXIV_VERSION_RE = re.compile(r"v\d+$")

from sqlalchemy import desc, func, select
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

# Status values returned by ``_tool_ingest_arxiv``. Strings (not StrEnum)
# because they're serialised to the LLM in tool output JSON; keeping them
# as named constants prevents typo-drift across the docstring + branches.
INGEST_STATUS_COMPLETE = "ingestion_complete"
INGEST_STATUS_PARTIAL = "ingestion_partial"
INGEST_STATUS_FAILED = "ingestion_failed"
# Papers landed in the corpus but the project-attach step failed. The LLM
# should NOT treat this as ordinary success; `link_error` carries the cause.
INGEST_STATUS_COMPLETE_LINK_FAILED = "ingestion_complete_link_failed"


def _escape_like(value: str) -> str:
    """Escape special LIKE pattern characters for safe ilike() queries."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Cache the LLM client used by summarize/compare tools at module scope so
# we don't pay the ~50ms client-build cost on every invocation. Mirrors the
# `_REFLECTION_LLM` pattern in src/services/agent/reflection.py.
_TOOL_LLM = None


def _get_tool_llm():
    """Return a cached LangChain chat model for use in tool implementations."""
    global _TOOL_LLM
    if _TOOL_LLM is not None:
        return _TOOL_LLM
    from src.services.agent.graph import _build_llm

    _TOOL_LLM = _build_llm()
    return _TOOL_LLM


# ---------------------------------------------------------------------------
# AGENT_TOOLS definition (tool schemas for OpenAI function calling)
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": "Search arXiv for academic papers. Use when the user asks to find, search, or look up research papers, academic publications, or scientific articles. Defaults sort to submittedDate (most recent first) and last-12-months window — pass recency_days=0 to disable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for arXiv papers (e.g., 'transformer attention mechanisms')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-5)",
                        "default": 5,
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "ArXiv categories to filter (e.g., ['cs.AI', 'cs.LG']). Optional.",
                    },
                    "recency_days": {
                        "type": "integer",
                        "description": "Only return papers submitted within the last N days. Default 365. Pass 0 to disable the date filter and search all-time.",
                        "default": 365,
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
            "name": "do_kb_retrieve",
            "description": (
                "Semantic retrieval over the organization's DigitalOcean Knowledge Base. "
                "Returns text chunks ranked by semantic similarity to the query. "
                "Use for content-level questions across ingested documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language query for semantic retrieval.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of chunks to return (1-20).",
                        "default": 8,
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
            "name": "create_project",
            "description": (
                "Create a new research project (folder) for organizing papers, "
                "documents, and notes. Use when the user asks to create, start, "
                "or set up a new project or research folder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Project name (1-255 chars)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional project description",
                    },
                    "research_goals": {
                        "type": "string",
                        "description": "Optional statement of the project's objectives and goals",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional categorization tags",
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": (
                            "Optional workspace UUID. If omitted, the user's "
                            "first workspace is used."
                        ),
                    },
                },
                "required": ["name"],
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
            "name": "list_projects",
            "description": (
                "List the user's research projects. Use when the user asks "
                "'what projects do I have', 'list my projects', or otherwise "
                "wants to discover existing projects before choosing one. "
                "Prefer this over asking the user to provide a project_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter by research status (e.g., 'active', 'archived')",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Optional tag to filter by",
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional substring match against project name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of projects to return (1-50, default 20)",
                        "default": 20,
                    },
                },
                "required": [],
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
            "description": "Extract named entities from a document using LLM analysis. Finds people, organizations, concepts, methods, models, datasets, and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document to extract entities from",
                    },
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional filter. Allowed types: PERSON, ORGANIZATION, CONCEPT, METHOD, MODEL, DATASET, TECHNOLOGY, METRIC, LOCATION, RESEARCH. Omit for all types.",
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
    {
        "type": "function",
        "function": {
            "name": "search_external_database",
            "description": (
                "Search external scientific and financial databases (PubMed, "
                "UniProt, ChEMBL, PubChem, ClinicalTrials.gov, SEC EDGAR, FRED, "
                "Alpha Vantage, ZINC, COSMIC, and 70+ BioServices databases). "
                "Use when the user needs data from domain-specific databases "
                "beyond arXiv. Specify a connector name to target one database, "
                "or a domain to search all databases in that category."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "connector": {
                        "type": "string",
                        "description": (
                            "Specific connector name (e.g., 'pubmed', 'uniprot', "
                            "'chembl', 'clinical_trials', 'sec_edgar', 'fred'). "
                            "Optional — if omitted, searches all available connectors "
                            "in the given domain."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Domain filter: 'biomedical', 'chemistry', 'genomics', "
                            "'finance', 'economic', 'clinical', 'literature'. "
                            "Optional — if omitted, searches all."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results per connector (1-20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_external_databases",
            "description": (
                "List all available external database connectors. Use when the "
                "user asks what databases are available, or to discover data "
                "sources for a specific domain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": (
                            "Filter by domain: 'biomedical', 'chemistry', "
                            "'genomics', 'finance', 'economic', 'clinical'"
                        ),
                    },
                },
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
    if tool_name == "do_kb_retrieve":
        return await _tool_do_kb_retrieve(args, db, current_user)
    if tool_name == "add_document_to_project":
        return await _tool_add_document_to_project(args, db, current_user)
    if tool_name == "create_project":
        return await _tool_create_project(args, db, current_user)
    if tool_name == "create_project_note":
        return await _tool_create_project_note(args, db, current_user)
    if tool_name == "list_projects":
        return await _tool_list_projects(args, db, current_user)
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
    if tool_name == "search_external_database":
        return await _tool_search_external_database(args)
    if tool_name == "list_external_databases":
        return await _tool_list_external_databases(args)
    return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


# In-process TTL cache for ``_tool_search_arxiv``. Trace 019e1a5a showed
# the planner firing 4 near-identical arXiv searches in <2 min, tripping
# the upstream 429 limiter. Keying on the normalized query lets repeated
# tool calls within ``_ARXIV_SEARCH_CACHE_TTL`` seconds reuse the prior
# result instead of hammering arxiv.org.
_ARXIV_SEARCH_CACHE: Dict[tuple, tuple[float, Dict[str, Any]]] = {}
_ARXIV_SEARCH_CACHE_TTL = 600.0  # 10 minutes
_ARXIV_SEARCH_CACHE_MAX = 64


def _arxiv_cache_key(
    query: str,
    max_results: int,
    categories: Optional[List[str]],
    recency_days: int,
) -> tuple:
    cats = tuple(sorted(categories)) if categories else ()
    return (query.strip(), int(max_results), cats, int(recency_days))


def _arxiv_cache_get(key: tuple) -> Optional[Dict[str, Any]]:
    import time

    hit = _ARXIV_SEARCH_CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.monotonic() - ts > _ARXIV_SEARCH_CACHE_TTL:
        _ARXIV_SEARCH_CACHE.pop(key, None)
        return None
    return value


def _arxiv_cache_set(key: tuple, value: Dict[str, Any]) -> None:
    import time

    if len(_ARXIV_SEARCH_CACHE) >= _ARXIV_SEARCH_CACHE_MAX:
        # Drop oldest. Small N so linear scan is fine.
        oldest = min(_ARXIV_SEARCH_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _ARXIV_SEARCH_CACHE.pop(oldest, None)
    _ARXIV_SEARCH_CACHE[key] = (time.monotonic(), value)


def _is_valid_uuid(value: Any) -> bool:
    """Return True if ``value`` parses as a UUID string."""
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


async def _tool_search_arxiv(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search arXiv for papers."""
    from datetime import datetime, timedelta, timezone

    from src.services.arxiv.arxiv_service import ArXivIngestionService

    query = args.get("query", "")
    # Hard cap at 5 papers + 250-char abstracts. Trace showed 10×500-char
    # results = 8087 chars feeding into the synthesis LLM call and triggering
    # 1536 reasoning tokens (~46s). Smaller payload = faster synthesis.
    max_results = min(args.get("max_results", 5), 5)
    categories = args.get("categories")

    # Recency window: default to last 12 months so "find recent X" actually
    # returns recent results. Trace 019e191a showed default search returning
    # papers from 2018-2024 (relevance-sorted) when user asked for "recent".
    # Pass recency_days=0 to disable the filter.
    recency_days_raw = args.get("recency_days", 365)
    try:
        recency_days = int(recency_days_raw)
    except (TypeError, ValueError):
        recency_days = 365
    # Clamp to ≥0; negative values silently disable the filter under the
    # > 0 check, but the contract is "0 disables, positive caps lookback".
    recency_days = max(0, recency_days)
    if recency_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)
        cutoff_str = cutoff.strftime("%Y%m%d%H%M")
        # arxiv API supports the `submittedDate:[FROM TO]` filter inside
        # the search_query parameter. Compose it AND the user's query.
        date_filter = f"submittedDate:[{cutoff_str} TO 999912312359]"
        query = f"({query}) AND {date_filter}" if query else date_filter

    cache_key = _arxiv_cache_key(query, max_results, categories, recency_days)
    cached = _arxiv_cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        async with ArXivIngestionService() as service:
            papers = await service.search_papers(
                query=query,
                max_results=max_results,
                categories=categories,
                # Sort by submission date so the "most recent" claim matches
                # what comes back, not relevance order across 30 years.
                sort_by="submittedDate",
                sort_order="descending",
            )
            results = []
            for p in papers[:max_results]:
                results.append(
                    {
                        "id": p.get("id", ""),
                        "title": p.get("title", ""),
                        "authors": p.get("authors", [])[:3],
                        "abstract": (p.get("abstract", "") or "")[:250],
                        "published": str(p.get("published", "")),
                        "categories": p.get("categories", []),
                        "pdf_url": p.get("pdf_url", ""),
                    }
                )
            payload = {"papers": results, "total": len(results), "query": query}
            _arxiv_cache_set(cache_key, payload)
            return payload
    except Exception as e:
        logger.error("ArXiv search tool failed", exc_info=e)
        # On 429 or other failure, fall back to a stale cache hit (any TTL)
        # so the LLM can proceed with prior results instead of looping.
        stale = _ARXIV_SEARCH_CACHE.get(cache_key)
        if stale is not None:
            return {
                **stale[1],
                "cached": True,
                "stale": True,
                "warning": f"ArXiv unavailable ({e}); returned cached results.",
            }
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
    project_id = args.get("project_id")
    if not paper_ids:
        return {"error": "No paper IDs provided"}
    if len(paper_ids) > 10:
        return {"error": "Maximum 10 papers per ingest request"}

    # Reject placeholder/hallucinated project_ids early so we don't ingest
    # papers we can't link. Trace 019e1a1c showed the planner passing
    # project_id="proj_12345" (non-UUID) and the tool happily continuing.
    if project_id is not None and not _is_valid_uuid(project_id):
        return {
            "error": (
                f"Invalid project_id {project_id!r}; expected a UUID. "
                "Call list_projects to find the correct ID, or omit "
                "project_id to ingest without project attachment."
            ),
            "error_type": "invalid_project_id",
            "paper_ids": paper_ids,
        }

    # Per-paper failure tracking. Keys are requested arXiv IDs; value is the
    # reason a paper didn't end up as an ingested Document. Empty on full
    # success.
    failed_papers: Dict[str, str] = {}

    try:
        async with ArXivIngestionService() as service:
            # Fetch paper metadata in parallel; cap concurrency to be polite
            # to the arXiv API (no batched id_list endpoint available).
            metadata_semaphore = asyncio.Semaphore(5)

            async def _fetch_one(pid: str) -> Dict[str, Any]:
                async with metadata_semaphore:
                    try:
                        results = await service.search_papers(
                            query=f"id:{pid}",
                            max_results=1,
                        )
                    except Exception as exc:
                        logger.warning(
                            "arXiv metadata fetch failed for %s: %s", pid, exc
                        )
                        failed_papers[pid] = f"metadata fetch failed: {exc}"
                        results = None
                if results:
                    return results[0]
                # Fallback: minimal paper dict so ingest can still proceed.
                # Record the miss so the caller knows which IDs lacked
                # real arXiv metadata (likely invalid or very new).
                failed_papers.setdefault(
                    pid,
                    "arXiv returned no metadata (invalid ID or paper not yet "
                    "indexed)",
                )
                return {
                    "id": pid,
                    "title": f"arXiv:{pid}",
                    "authors": [],
                    "abstract": "",
                    "published": "",
                    "updated": "",
                    "categories": [],
                    "links": {"pdf": f"https://arxiv.org/pdf/{pid}"},
                }

            papers_to_ingest = list(
                await asyncio.gather(*[_fetch_one(pid) for pid in paper_ids])
            )

            ingested = await service.ingest_papers(
                papers=papers_to_ingest,
                download_pdfs=True,
                extract_content=True,
            )

            # Detect which requested paper_ids the service dropped during
            # download/extract so we can surface per-paper failure reasons
            # instead of a generic zero-count message.
            # arXiv returns versioned IDs (``2605.10877v1``) while callers
            # typically pass unversioned IDs — strip ``vN`` before comparing
            # so successfully ingested papers aren't flagged as failures.
            def _strip_version(aid: str) -> str:
                return _ARXIV_VERSION_RE.sub("", aid)

            ingested_arxiv_ids: set[str] = set()
            for doc in ingested or []:
                meta = getattr(doc, "document_metadata", None) or {}
                aid = meta.get("arxiv_id") if isinstance(meta, dict) else None
                if aid:
                    ingested_arxiv_ids.add(_strip_version(str(aid)))
            for pid in paper_ids:
                if (
                    _strip_version(pid) not in ingested_arxiv_ids
                    and pid not in failed_papers
                ):
                    failed_papers[pid] = (
                        "PDF download or content extraction failed"
                    )

            document_ids = []
            if ingested and current_user:
                # Use a fresh DB session to avoid concurrency issues with the
                # shared graph session (same pattern as _tool_add_document_to_project).
                from src.core.database import AsyncSessionLocal

                try:
                    persisted_documents: List[Document] = []
                    async with AsyncSessionLocal() as fresh_db:
                        async with fresh_db.begin():
                            for doc in ingested:
                                document = Document(
                                    title=getattr(doc, "title", "Untitled"),
                                    filename=getattr(doc, "filename", ""),
                                    file_path=getattr(
                                        doc,
                                        "file_path",
                                        getattr(doc, "filename", ""),
                                    ),
                                    file_size_bytes=getattr(doc, "file_size_bytes", 0),
                                    mime_type=getattr(
                                        doc, "mime_type", "application/pdf"
                                    ),
                                    document_type=DocumentType.PDF,
                                    content_text=getattr(doc, "content_text", None),
                                    content_summary=getattr(
                                        doc, "content_summary", None
                                    ),
                                    document_metadata=_sanitize_metadata(
                                        getattr(doc, "document_metadata", {})
                                    ),
                                    processing_status=ProcessingStatus.COMPLETED,
                                    uploaded_by_user_id=current_user.id,
                                    organization_id=current_user.organization_id,
                                    is_public=False,
                                )
                                fresh_db.add(document)
                                await fresh_db.flush()
                                document_ids.append(str(document.id))
                                persisted_documents.append(document)
                            # begin() auto-commits on exit
                    logger.info(
                        "Ingested %d documents to DB: %s",
                        len(document_ids),
                        document_ids,
                    )

                    # Phase 2 dual-write: mirror into DO KB. Failure-isolated.
                    from src.core.config import settings as _kb_settings

                    if getattr(_kb_settings, "DO_KB_ENABLED", False) and persisted_documents:
                        try:
                            from src.services.do_kb import sync_documents_to_kb

                            async with AsyncSessionLocal() as kb_db:
                                merged = [
                                    await kb_db.merge(d) for d in persisted_documents
                                ]
                                await sync_documents_to_kb(kb_db, merged)
                        except Exception as kb_err:  # noqa: BLE001
                            logger.warning(
                                "do_kb dual-write skipped for arxiv ingest: %s", kb_err
                            )
                except Exception as db_err:
                    logger.error(
                        "Failed to persist ingested documents to DB", exc_info=db_err
                    )
                    document_ids = []
                    return {
                        "error": f"Papers downloaded but DB persist failed: {str(db_err)}"
                    }
            elif ingested:
                # Fallback: no current_user, return paper_ids only
                for doc in ingested:
                    doc_id = getattr(doc, "id", None)
                    if doc_id:
                        document_ids.append(str(doc_id))

            # Auto-attach to active project if one is in context.
            linked_project_id: Optional[str] = None
            linked_project_name: Optional[str] = None
            link_error: Optional[str] = None
            if project_id and document_ids and current_user:
                from src.api.agent.tool_helpers import _link_documents_to_project
                from src.core.database import AsyncSessionLocal as _LinkSession

                try:
                    async with _LinkSession() as link_db:
                        project = await _verify_project_ownership(
                            project_id, link_db, current_user
                        )
                        if not project:
                            link_error = (
                                f"Project '{project_id}' not found or access denied; "
                                "documents ingested but NOT attached."
                            )
                        else:
                            result = await _link_documents_to_project(
                                link_db, project, document_ids
                            )
                            await link_db.commit()
                            linked_project_id = str(project.id)
                            linked_project_name = project.name
                            logger.info(
                                "Linked %d (skipped %d already-linked) ingested "
                                "docs to project %s (%s)",
                                result["linked"],
                                result["already_linked"],
                                linked_project_id,
                                linked_project_name,
                            )
                except Exception as link_err:
                    logger.error(
                        "Failed to link ingested docs to project %s", project_id,
                        exc_info=link_err,
                    )
                    link_error = f"Project link failed: {link_err}"

            ingested_count = len(document_ids)
            requested_count = len(paper_ids)

            # Classify outcome so the LLM doesn't read "ingestion_complete"
            # as success when zero papers actually landed.
            if ingested_count == 0:
                status = INGEST_STATUS_FAILED
                message = (
                    f"Ingested 0 of {requested_count} paper(s). The arXiv IDs "
                    "may be invalid, very new (not yet on arxiv.org), or the "
                    "download/extract step failed. Try again with different "
                    "IDs or wait a few hours for very recent papers."
                )
            elif ingested_count < requested_count:
                status = INGEST_STATUS_PARTIAL
                message = (
                    f"Ingested {ingested_count} of {requested_count} paper(s). "
                    f"{requested_count - ingested_count} failed — likely "
                    "invalid IDs or download errors."
                )
            else:
                status = INGEST_STATUS_COMPLETE
                message = f"Ingested {ingested_count} paper(s) into the RAG system."

            if linked_project_name:
                message += f" Attached to project '{linked_project_name}'."

            # Promote link failure to a distinct status so the LLM doesn't
            # confuse "ingested fine but never attached" with full success.
            if link_error and status == INGEST_STATUS_COMPLETE:
                status = INGEST_STATUS_COMPLETE_LINK_FAILED

            failed_papers_list = [
                {"paper_id": pid, "reason": reason}
                for pid, reason in failed_papers.items()
            ]
            if failed_papers_list and ingested_count == 0:
                # Append per-paper failure detail so the LLM/user can see
                # exactly which IDs failed and why.
                reasons = ", ".join(
                    f"{fp['paper_id']} ({fp['reason']})"
                    for fp in failed_papers_list
                )
                message += f" Details: {reasons}."

            return {
                "status": status,
                "paper_ids": paper_ids,
                "document_ids": document_ids,
                "ingested_count": ingested_count,
                "requested_count": requested_count,
                "failed_papers": failed_papers_list,
                "project_id": linked_project_id,
                "project_name": linked_project_name,
                "link_error": link_error,
                "message": message,
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
                    "status": (
                        d.processing_status.value if d.processing_status else None
                    ),
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


async def _tool_do_kb_retrieve(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Semantic retrieval over the org's DigitalOcean Knowledge Base.

    Returns an empty chunks list when the org has no provisioned KB or
    when DO_KB_ENABLED is false — caller falls back to other tools.
    """
    if not current_user:
        return {"error": "Authentication required", "chunks": [], "total": 0}

    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "Query is required", "chunks": [], "total": 0}

    from src.core.config import settings as _kb_settings

    top_k = max(1, min(int(args.get("top_k", _kb_settings.DO_KB_DEFAULT_TOP_K)), 20))

    if not getattr(_kb_settings, "DO_KB_ENABLED", False):
        return {"chunks": [], "total": 0, "source": "do_kb", "reason": "disabled"}

    # Read kb_uuid from the org. Lazy import to keep cold-start light.
    kb_uuid: Optional[str] = None
    if db is not None:
        from src.models.organization import Organization

        org = await db.get(Organization, current_user.organization_id)
        kb_uuid = getattr(org, "do_kb_uuid", None) if org else None

    if not kb_uuid:
        return {"chunks": [], "total": 0, "source": "do_kb", "reason": "not_provisioned"}

    try:
        from src.services.do_kb import get_do_kb_client

        client = get_do_kb_client()
        result = await client.retrieve(kb_uuid=kb_uuid, query=query, top_k=top_k)
    except Exception as exc:
        logger.warning("do_kb_retrieve failed: %s", exc)
        return {
            "chunks": [],
            "total": 0,
            "source": "do_kb",
            "error": f"Retrieval failed: {exc}",
        }

    # Resolve storage-key document_ids back to real Document rows and
    # optionally filter by project membership.
    project_id = args.get("project_id")
    title_by_key: dict[str, tuple[str, str]] = {}
    chunks_to_emit = result.chunks
    if db is not None and result.chunks:
        from src.services.do_kb.resolve import resolve_and_filter_chunks

        title_by_key, chunks_to_emit = await resolve_and_filter_chunks(
            chunks=result.chunks,
            org_id=current_user.organization_id,
            session=db,
            project_id=project_id,
        )

    chunks_payload = []
    for c in chunks_to_emit:
        resolved_id, title = title_by_key.get(c.document_id or "", (None, None))
        chunks_payload.append(
            {
                "text": c.text,
                "score": c.score,
                "document_id": resolved_id or c.document_id,
                "title": title or (c.metadata or {}).get("title") or c.document_id,
                "metadata": c.metadata,
            }
        )
    return {
        "chunks": chunks_payload,
        "total": len(chunks_payload) if project_id else result.total,
        "source": "do_kb",
        "query": query,
    }


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
            project = await _verify_project_ownership(
                project_id, fresh_db, current_user
            )
            if not project:
                return {"error": "Project not found or access denied"}

            from src.api.agent.tool_helpers import _link_documents_to_project

            result = await _link_documents_to_project(
                fresh_db, project, [str(doc_uuid)]
            )
            await fresh_db.commit()

            if result["linked"] == 0 and result["already_linked"] >= 1:
                return {
                    "status": "already_linked",
                    "message": f"Document '{doc.title}' is already in project '{project.name}'.",
                }

            return {
                "status": "success",
                "message": f"Added document '{doc.title}' to project '{project.name}'.",
                "document_id": str(doc.id),
                "project_id": str(project.id),
            }
    except Exception as e:
        logger.error("add_document_to_project tool failed", exc_info=e)
        return {"error": f"Failed to add document to project: {str(e)}"}


async def _tool_create_project(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Create a new research project.

    If ``workspace_id`` is omitted, the user's first workspace is used.
    """
    if not current_user:
        return {"error": "Authentication required"}

    name = (args.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}

    from src.core.database import AsyncSessionLocal
    from src.services.research.project_service import ProjectService
    from src.shared.research_schemas import ProjectCreate

    try:
        async with AsyncSessionLocal() as fresh_db:
            service = ProjectService(fresh_db)

            workspace_id_raw = args.get("workspace_id")
            if workspace_id_raw:
                try:
                    workspace_id = UUID(str(workspace_id_raw))
                except ValueError:
                    return {"error": "workspace_id must be a valid UUID"}
            else:
                workspace_ids = await service._get_workspace_ids_for_user(
                    current_user.id
                )
                if not workspace_ids:
                    return {
                        "error": (
                            "No workspace found for user. Create a workspace first."
                        )
                    }
                workspace_id = workspace_ids[0]

            payload = ProjectCreate(
                workspace_id=workspace_id,
                name=name,
                description=args.get("description") or None,
                research_goals=args.get("research_goals") or None,
                tags=list(args.get("tags") or []),
            )

            project = await service.create_project(
                user_id=current_user.id,
                project_data=payload,
            )

            return {
                "status": "success",
                "project_id": str(project.id),
                "name": project.name,
                "workspace_id": str(project.workspace_id),
                "message": f"Created project '{project.name}'.",
            }
    except Exception as e:
        logger.error("create_project tool failed", exc_info=e)
        return {"error": f"Failed to create project: {str(e)}"}


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
            project = await _verify_project_ownership(
                project_id, fresh_db, current_user
            )
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

    raw_limit = args.get("limit", 100)
    try:
        limit = max(1, min(int(raw_limit), 500))
    except (TypeError, ValueError):
        limit = 100
    raw_offset = args.get("offset", 0)
    try:
        offset = max(0, int(raw_offset))
    except (TypeError, ValueError):
        offset = 0

    try:
        # Verify project ownership (resolves UUID or name)
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        base_where = (
            CollectionDocument.collection_id == project.id,
            Document.is_deleted == False,
        )

        count_stmt = (
            select(func.count())
            .select_from(Document)
            .join(CollectionDocument, CollectionDocument.document_id == Document.id)
            .where(*base_where)
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Document)
            .join(CollectionDocument, CollectionDocument.document_id == Document.id)
            .where(*base_where)
            .order_by(desc(Document.created_at))
            .offset(offset)
            .limit(limit)
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
                    "status": (
                        d.processing_status.value if d.processing_status else None
                    ),
                }
                for d in docs
            ],
            "total": int(total),
            "returned": len(docs),
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(docs) < int(total),
        }
    except Exception as e:
        logger.error("list_project_documents tool failed", exc_info=e)
        return {"error": f"Failed to list project documents: {str(e)}"}


async def _tool_list_projects(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """List research projects owned by the current user.

    Thin wrapper around :meth:`ProjectService.list_projects` that returns a
    compact payload suitable for LLM context. Uses a fresh DB session to
    avoid conflicts with the shared graph session.
    """
    if not current_user:
        return {"error": "Authentication required"}

    raw_limit = args.get("limit", 20)
    try:
        limit = max(1, min(int(raw_limit), 50))
    except (TypeError, ValueError):
        limit = 20

    status = (args.get("status") or "").strip() or None
    tag = (args.get("tag") or "").strip() or None
    search = (args.get("search") or "").strip() or None

    from src.core.database import AsyncSessionLocal
    from src.services.research.project_service import ProjectService

    try:
        async with AsyncSessionLocal() as fresh_db:
            service = ProjectService(fresh_db)
            result = await service.list_projects(
                user_id=current_user.id,
                project_status=status,
                tag=tag,
                search=search,
                skip=0,
                limit=limit,
            )

            projects = result.get("projects", [])
            return {
                "projects": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "description": getattr(p, "description", None),
                        "status": getattr(p, "research_status", None),
                        "tags": list(getattr(p, "tags", []) or []),
                        "updated_at": (
                            p.updated_at.isoformat()
                            if getattr(p, "updated_at", None)
                            else None
                        ),
                    }
                    for p in projects
                ],
                "total": result.get("total", len(projects)),
                "returned": len(projects),
            }
    except Exception as e:
        logger.error("list_projects tool failed", exc_info=e)
        return {"error": f"Failed to list projects: {str(e)}"}


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
            # Helpful hint when the input looks like an arXiv ID but the
            # paper hasn't been ingested into the workspace yet.
            import re as _re

            if _re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", (document_id or "").strip()):
                return {
                    "error": (
                        f"Document with arXiv ID '{document_id}' is not in your "
                        "library. Use ingest_arxiv_papers([\""
                        f"{document_id}\"]) first, then retry summarize_document "
                        "with the returned internal document_id."
                    ),
                    "error_type": "recoverable",
                    "suggestion": "ingest_arxiv_papers",
                }
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
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = _get_tool_llm()
            response = await llm.ainvoke(
                [
                    SystemMessage(
                        content="You are a research assistant. Provide a concise summary of the following document in 3-5 paragraphs. Focus on key findings, methodology, and conclusions."
                    ),
                    HumanMessage(content=text_for_summary),
                ]
            )
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

        # Resolve all UUID-shaped IDs in a single batched query; only fall
        # back to per-id title lookups for non-UUID inputs. AsyncSession is
        # not safe for concurrent statements, so we keep title fallbacks
        # serial.
        uuid_inputs: list[tuple[str, UUID]] = []
        title_inputs: list[str] = []
        for did in document_ids:
            try:
                uuid_inputs.append((did, UUID(did)))
            except (ValueError, AttributeError, TypeError):
                title_inputs.append(did)

        docs_by_uuid: Dict[UUID, Document] = {}
        if uuid_inputs:
            uuid_stmt = select(Document).where(
                Document.id.in_([u for _, u in uuid_inputs]),
                Document.organization_id == current_user.organization_id,
                Document.is_deleted == False,
            )
            for doc in (await db.execute(uuid_stmt)).scalars().all():
                docs_by_uuid[doc.id] = doc

        resolved: Dict[str, Document] = {}
        for raw_id, parsed in uuid_inputs:
            doc = docs_by_uuid.get(parsed)
            if doc is not None:
                resolved[raw_id] = doc

        for raw_id in title_inputs:
            doc = await _resolve_document_id(raw_id, db, current_user)
            if doc is not None:
                resolved[raw_id] = doc

        doc_texts = []
        for did in document_ids:
            doc = resolved.get(did)
            if not doc:
                return {"error": f"Document not found: {did}"}

            text = doc.content_text or ""
            if not text:
                text = file_service.extract_text_content(doc)

            doc_texts.append(
                {
                    "id": str(doc.id),
                    "title": doc.title or "Untitled",
                    "text": text[:4000],
                }
            )

        # Use LLM to compare
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = _get_tool_llm()
            docs_content = "\n\n---\n\n".join(
                f"Document: {d['title']}\n{d['text']}" for d in doc_texts
            )
            response = await llm.ainvoke(
                [
                    SystemMessage(
                        content=f"You are a research assistant. Compare the following documents ({comparison_type} comparison). Identify similarities, differences, and key themes across them. Be structured and concise."
                    ),
                    HumanMessage(content=docs_content),
                ]
            )
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
    db: Any,
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Extract named entities from a document using LLM."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    if not document_id:
        return {"error": "document_id is required"}

    entity_types = args.get("entity_types")

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

        from src.services.processing.llm_entity_extraction import (
            LLMEntityExtractionService,
        )

        service = LLMEntityExtractionService()
        result = await service.extract_entities(text, entity_types=entity_types)

        if result.entities:
            return {
                "entities": [
                    {
                        "name": e.name,
                        "type": e.type,
                        "description": e.description,
                        "confidence": e.confidence,
                        "aliases": e.aliases,
                    }
                    for e in result.entities[:50]
                ],
                "total": len(result.entities),
                "chunks_processed": result.chunks_processed,
                "document_id": document_id,
                "title": doc.title or "Untitled",
            }

        return {
            "entities": [],
            "total": 0,
            "document_id": document_id,
            "error": result.error,
        }
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
        from src.models.graph import EntityType
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        type_filters = None
        if entity_types:
            type_filters = []
            for et in entity_types:
                try:
                    type_filters.append(EntityType(et.upper()))
                except ValueError:
                    pass

        loop = asyncio.get_running_loop()
        entities = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.search_entities(
                    query=query,
                    entity_types=type_filters,
                    limit=limit,
                ),
            ),
            timeout=15.0,
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
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        loop = asyncio.get_running_loop()
        neighborhood = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.get_neighborhood(
                    entity_id=entity_id,
                    max_depth=max_depth,
                    limit=limit,
                ),
            ),
            timeout=15.0,
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
                    "type": (
                        r.relationship_type.value
                        if r.relationship_type
                        else "RELATED_TO"
                    ),
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
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        loop = asyncio.get_running_loop()
        paths = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.find_paths(
                    source_id=source_id,
                    target_id=target_id,
                    max_depth=max_depth,
                ),
            ),
            timeout=15.0,
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
                        {
                            "id": e.id,
                            "name": e.name,
                            "type": e.entity_type.value if e.entity_type else "UNKNOWN",
                        }
                        for e in p.entities
                    ],
                    "relationships": [
                        {
                            "source": r.source_entity_id,
                            "target": r.target_entity_id,
                            "type": (
                                r.relationship_type.value
                                if r.relationship_type
                                else "RELATED_TO"
                            ),
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
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        loop = asyncio.get_running_loop()
        analytics = await asyncio.wait_for(
            loop.run_in_executor(None, knowledge_graph_service.get_graph_analytics),
            timeout=15.0,
        )

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
        from src.services.research.draft_generation_service import (
            DraftGenerationService,
        )

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


@dataclass
class _CitationProxy:
    """Lightweight stand-in for Citation ORM objects.

    BibliographyService reads these attributes via duck typing — no DB row
    required.  Built from Document.document_metadata when no Citation records
    exist for a document.
    """

    document_title: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    abstract: Optional[str] = None


def _citations_from_documents(documents: list) -> List[_CitationProxy]:
    """Build CitationProxy objects from Document.document_metadata."""
    proxies: List[_CitationProxy] = []
    for doc in documents:
        meta = doc.document_metadata or {}
        year = None
        pub_date = meta.get("publication_date")
        if pub_date:
            try:
                if isinstance(pub_date, str):
                    year = int(pub_date[:4])
                elif hasattr(pub_date, "year"):
                    year = pub_date.year
            except (ValueError, TypeError):
                pass
        proxies.append(
            _CitationProxy(
                document_title=meta.get("title") or doc.title or "",
                authors=meta.get("authors") or [],
                year=year,
                venue=meta.get("journal_reference"),
                doi=meta.get("doi"),
                arxiv_id=meta.get("arxiv_id"),
                abstract=meta.get("description"),
            )
        )
    return proxies


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
        return {
            "error": f"Unsupported format: {bib_format}. Use bibtex, apa, ieee, or mla."
        }

    # Parse and dedupe UUIDs in one pass; ignore malformed inputs
    valid_uuids: list[UUID] = []
    for did in document_ids:
        try:
            valid_uuids.append(UUID(did))
        except (ValueError, AttributeError, TypeError):
            continue
    if not valid_uuids:
        return {
            "bibliography": "",
            "format": bib_format,
            "count": 0,
            "message": "No valid document IDs supplied.",
        }

    try:
        # Batch ownership check: only documents in the user's organization
        owned_stmt = select(Document).where(
            Document.id.in_(valid_uuids),
            Document.organization_id == current_user.organization_id,
            Document.is_deleted == False,
        )
        owned_result = await db.execute(owned_stmt)
        owned_docs = list(owned_result.scalars().all())
        if not owned_docs:
            return {
                "bibliography": "",
                "format": bib_format,
                "count": 0,
                "message": "No accessible documents found for the given IDs.",
            }

        owned_ids = [d.id for d in owned_docs]

        # Batch citation fetch for accessible documents
        citation_stmt = select(Citation).where(Citation.document_id.in_(owned_ids))
        citation_result = await db.execute(citation_stmt)
        citations = list(citation_result.scalars().all())

        # Fallback: build bibliography from Document metadata when no
        # Citation records exist (common for freshly ingested papers).
        if not citations:
            proxies = _citations_from_documents(owned_docs)
            if not proxies:
                return {
                    "bibliography": "",
                    "format": bib_format,
                    "count": 0,
                    "message": "No citations found for the given documents.",
                }
            citations = proxies

        from src.services.research.bibliography_service import BibliographyService

        bibliography = BibliographyService.format_bibliography(
            citations, bib_format  # type: ignore[arg-type]
        )

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
        return {"error": "Code execution is not available. E2B_API_KEY not configured."}

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


# ---------------------------------------------------------------------------
# External database connector tools
# ---------------------------------------------------------------------------


async def _tool_search_external_database(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search external databases via the connector registry."""
    import asyncio

    from src.services.connectors import connector_registry
    from src.services.connectors.base import ConnectorDomain

    query = args.get("query", "")
    if not query:
        return {"error": "query is required"}

    connector_name = args.get("connector")
    domain_name = args.get("domain")
    max_results = min(args.get("max_results", 5), 20)

    try:
        if connector_name:
            connector = connector_registry.get(connector_name)
            if connector is None:
                available = [c.info.name for c in connector_registry.list_all()]
                return {
                    "error": f"Unknown connector: {connector_name}",
                    "available_connectors": available,
                }
            if not connector.is_available():
                return {
                    "error": (
                        f"Connector '{connector_name}' requires API key "
                        f"({connector.info.api_key_env_var})"
                    )
                }
            targets = [connector]
        elif domain_name:
            try:
                domain = ConnectorDomain(domain_name)
            except ValueError:
                return {
                    "error": f"Invalid domain: {domain_name}",
                    "valid_domains": [d.value for d in ConnectorDomain],
                }
            targets = connector_registry.search_by_domain(domain)
        else:
            targets = connector_registry.list_available()

        if not targets:
            return {"error": "No available connectors found for the given criteria"}

        tasks = [c.search(query, max_results=max_results) for c in targets]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        connectors_searched = []
        for connector, result in zip(targets, all_results):
            connectors_searched.append(connector.info.name)
            if isinstance(result, Exception):
                logger.warning(
                    "connector_search_failed",
                    connector=connector.info.name,
                    error=str(result),
                )
                continue
            for r in result:
                results.append(
                    {
                        "id": r.id,
                        "title": r.title,
                        "source": r.source,
                        "url": r.url,
                        "content": r.content[:300],
                        "authors": r.authors[:5],
                        "published_date": r.published_date,
                        "document_type": r.document_type,
                    }
                )

        return {
            "query": query,
            "total_results": len(results),
            "results": results,
            "connectors_searched": connectors_searched,
        }
    except Exception as exc:
        logger.exception("external_db_search_failed")
        return {"error": f"Search failed: {str(exc)}"}


async def _tool_list_external_databases(args: Dict[str, Any]) -> Dict[str, Any]:
    """List available external database connectors."""
    from src.services.connectors import connector_registry
    from src.services.connectors.base import ConnectorDomain

    domain_name = args.get("domain")

    if domain_name:
        try:
            domain = ConnectorDomain(domain_name)
        except ValueError:
            return {
                "error": f"Invalid domain: {domain_name}",
                "valid_domains": [d.value for d in ConnectorDomain],
            }
        connectors = connector_registry.search_by_domain(domain)
    else:
        connectors = connector_registry.list_all()

    return {
        "total": len(connectors),
        "available": sum(1 for c in connectors if c.is_available()),
        "connectors": [
            {
                "name": c.info.name,
                "display_name": c.info.display_name,
                "description": c.info.description,
                "domains": [d.value for d in c.info.domains],
                "capabilities": [cap.value for cap in c.info.capabilities],
                "requires_api_key": c.info.requires_api_key,
                "available": c.is_available(),
            }
            for c in connectors
        ],
    }


async def _tool_forget_memory(
    *,
    query: str,
    user_id: str,
    page_context: dict | None = None,
) -> dict:
    """Handler for the forget_memory agent tool."""
    if not user_id:
        return {"error": "forget_memory: missing user_id from config"}
    if not query or not query.strip():
        return {"error": "forget_memory: empty query"}

    from src.services.agent.memory import (
        delete_memory_by_query,
        get_memory_store,
    )

    store = await get_memory_store()
    if store is None:
        return {"error": "forget_memory: memory store unavailable"}

    result = await delete_memory_by_query(
        store, user_id=user_id, query=query, limit=5
    )
    return {
        "status": "completed",
        "deleted": result["deleted"],
        "matches": result["matches"],
    }
