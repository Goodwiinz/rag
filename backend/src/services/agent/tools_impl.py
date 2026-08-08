"""Agent tool implementations.

Contains all _tool_* functions and the execute_tool dispatcher.
Each function performs a specific action (search, ingest, summarize, etc.)
and returns a dict result.
"""

import asyncio
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# Matches the trailing ``vN`` revision suffix arXiv appends to paper IDs
# (e.g. ``2605.10877v1``). Used to compare requested vs. ingested IDs
# without false negatives across version bumps.
_ARXIV_VERSION_RE = re.compile(r"v\d+$")

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.collection import CollectionDocument
from src.models.document import Document
from src.models.user import User

from .tool_helpers import (
    _escape_like,
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

# Statuses that mean the requested work did not happen. Mirrors
# ``reflection._INGEST_FAILURE_STATUSES``; kept in sync deliberately.
_INGEST_FAILURE_STATUSES = frozenset({INGEST_STATUS_FAILED, INGEST_STATUS_PARTIAL})


# Cache the LLM client used by summarize/compare tools at module scope so
# we don't pay the ~50ms client-build cost on every invocation. Mirrors the
# `_REFLECTION_LLM` pattern in src/services/agent/reflection.py.
_TOOL_LLM = None
_TOOL_LLM_LOCK = threading.Lock()


def _get_tool_llm():
    """Return a cached LangChain chat model for use in tool implementations."""
    global _TOOL_LLM
    if _TOOL_LLM is not None:
        return _TOOL_LLM
    with _TOOL_LLM_LOCK:
        if _TOOL_LLM is not None:  # re-check inside lock
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
            "description": "Search arXiv for academic papers. Use when the user asks to find, search, or look up research papers, academic publications, or scientific articles. Pass clean topic KEYWORDS in `query` (e.g. 'retrieval-augmented generation', 'transformer attention mechanisms') — NOT filler words like 'recent', 'papers', or 'latest'; recency is controlled by `recency_days` and chronological ranking by `chronological`. Default: relevance-ranked results within the last 12 months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic keywords for arXiv search (e.g., 'retrieval-augmented generation'). Omit filler words like 'recent', 'papers', 'latest' — use recency_days for time-bounding.",
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
                    "chronological": {
                        "type": "boolean",
                        "description": "If true, sort results by submission date (newest first) instead of relevance. Default false (relevance ranking).",
                        "default": False,
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


def _registry_descriptor(tool_name: str):
    """Resolve code-owned tool metadata without importing wrappers eagerly."""
    from src.services.agent.tools import TOOL_REGISTRY

    return TOOL_REGISTRY.descriptor(tool_name)


async def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    user_id: str = "",
    organization_id: str = "",
    thread_id: str = "",
    runtime_snapshot_id: str = "",
    project_id: str = "",
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Execute an agent tool and return the result.

    This is the boundary where scalar identifiers become a session + user
    (audit B8): the LangGraph ``configurable`` carries ids only, so the
    production path calls this with ``user_id`` / ``organization_id`` /
    ``thread_id`` and the dispatcher opens a fresh tool-call-scoped session
    via :func:`~src.services.agent.tool_session.tool_session` and re-loads
    the acting user org-scoped via ``resolve_tool_user``.

    ``db`` / ``current_user`` remain as an explicit injection seam for
    direct callers and tests; when either is provided no session is opened
    and the values are forwarded as-is.
    """
    descriptor = _registry_descriptor(tool_name)
    if descriptor is None or not descriptor.enabled:
        return {"error": f"Unknown tool: {tool_name}"}

    from src.services.agent.tool_registry import ToolPolicyTag

    if descriptor and ToolPolicyTag.CONTEXT_FREE in descriptor.policy_tags:
        return await _dispatch_tool(
            tool_name,
            args,
            user_id,
            db,
            current_user,
            thread_id,
            runtime_snapshot_id,
            project_id,
        )

    if db is not None or current_user is not None:
        return await _dispatch_tool(
            tool_name,
            args,
            user_id,
            db,
            current_user,
            thread_id,
            runtime_snapshot_id,
            project_id,
        )

    from src.services.agent.tool_session import resolve_tool_user, tool_session

    async with tool_session() as session:
        resolved_user = await resolve_tool_user(session, user_id, organization_id)
        # End the resolve transaction so the connection returns to the pool
        # while a slow tool body (LLM call, arXiv download) runs;
        # expire_on_commit=False keeps the loaded User usable and the tool's
        # own statements transparently begin a new transaction.
        await session.commit()
        return await _dispatch_tool(
            tool_name,
            args,
            user_id,
            session,
            resolved_user,
            thread_id,
            runtime_snapshot_id,
            project_id,
        )


async def _dispatch_tool(
    tool_name: str,
    args: Dict[str, Any],
    user_id: str = "",
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
    thread_id: str = "",
    runtime_snapshot_id: str = "",
    project_id: str = "",
) -> Dict[str, Any]:
    """Route a tool call to its ``_tool_*`` implementation."""
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
        return await _tool_search_knowledge_graph(args, current_user)
    if tool_name == "explore_entity_neighborhood":
        return await _tool_explore_entity_neighborhood(args, current_user)
    if tool_name == "find_entity_paths":
        return await _tool_find_entity_paths(args, current_user)
    if tool_name == "get_graph_stats":
        return await _tool_get_graph_stats(args, current_user)
    if tool_name == "create_draft":
        return await _tool_create_draft(args, db, current_user)
    if tool_name == "export_bibliography":
        return await _tool_export_bibliography(args, db, current_user)
    if tool_name == "execute_code":
        return await _tool_execute_code(
            args, thread_id=thread_id, current_user=current_user
        )
    if tool_name == "search_external_database":
        return await _tool_search_external_database(args)
    if tool_name == "list_external_databases":
        return await _tool_list_external_databases(args)
    if tool_name == "forget_memory":
        return await _tool_forget_memory(
            query=args.get("query", ""),
            user_id=user_id,
            page_context=None,
        )
    if tool_name == "load_project_skill":
        return await _tool_load_project_skill(
            args,
            user_id=user_id,
            project_id=project_id,
            runtime_snapshot_id=runtime_snapshot_id,
            db=db,
        )
    return {"error": f"Unknown tool: {tool_name}"}


async def _tool_load_project_skill(
    args: Dict[str, Any],
    *,
    user_id: str,
    project_id: str,
    runtime_snapshot_id: str,
    db: Optional[AsyncSession],
) -> Dict[str, Any]:
    """Load a frozen skill through the snapshot service, never live pointers."""
    if db is None:
        return {
            "error_type": "runtime_snapshot_unavailable",
            "error": "Project skill loading requires a server session.",
        }
    from src.services.agent.runtime_snapshot import load_project_skill_from_snapshot

    return await load_project_skill_from_snapshot(
        db,
        snapshot_id=runtime_snapshot_id,
        user_id=user_id,
        project_id=project_id,
        skill_name=args.get("skill_name", ""),
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


# Two-layer cache for ``_tool_search_arxiv`` to avoid re-hitting arxiv.org's
# per-IP 429 limiter. L1 is a per-process in-memory dict (fast; protects a
# single planner firing 4 near-identical searches in <2 min — trace 019e1a5a).
# L2 (defined after the stopword list) is a SHARED Redis cache so the 1-5 HPA
# replicas + the synthetic CronJob reuse each other's results and near-duplicate
# phrasings collapse to one normalized key. Redis-down degrades to L1 only.
#
# L2 entries live ``_ARXIV_CACHE_STALE_TTL`` seconds but only count as a FRESH
# hit within ``_ARXIV_CACHE_FRESH_TTL``; the older band is the stale-on-429
# fallback (serve the last known result when arXiv is rate-limited).
_ARXIV_SEARCH_CACHE: Dict[tuple, tuple[float, Dict[str, Any]]] = {}
_ARXIV_CACHE_FRESH_TTL = 600.0  # 10 min: served as a fresh cache hit
_ARXIV_CACHE_STALE_TTL = 1800  # 30 min: kept in Redis for the 429 stale fallback
_ARXIV_SEARCH_CACHE_MAX = 64
_ARXIV_CACHE_REDIS_PREFIX = "arxiv:search:"  # own namespace; NOT tenant-scoped search:


def _arxiv_cache_key(
    query: str,
    max_results: int,
    categories: Optional[List[str]],
    recency_days: int,
    chronological: bool = False,
) -> tuple:
    cats = tuple(sorted(categories)) if categories else ()
    return (
        query.strip(),
        int(max_results),
        cats,
        int(recency_days),
        bool(chronological),
    )


def _arxiv_cache_get(key: tuple) -> Optional[Dict[str, Any]]:
    import time

    hit = _ARXIV_SEARCH_CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.monotonic() - ts > _ARXIV_CACHE_FRESH_TTL:
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


# Filler/recency words that add noise to arXiv's all-field search index.
# The model is instructed to pass clean keywords, but LLM output often leaks
# these tokens (e.g. "recent papers on RAG"). Stripping them before composing
# the `search_query` prevents them from diluting relevance scores.
_ARXIV_STOPWORDS = {
    "recent",
    "recently",
    "latest",
    "newest",
    "new",
    "papers",
    "paper",
    "articles",
    "on",
    "about",
    "for",
    "the",
    "a",
    "an",
    "find",
    "search",
    "me",
    "please",
}


def _sanitize_arxiv_query(q: str) -> str:
    """Drop leading recency/filler tokens so they don't pollute arXiv's
    all-field search (e.g. 'recent papers on RAG' -> 'RAG'). Conservative:
    only strips known stopwords, preserves the meaningful remainder verbatim;
    returns the original if stripping would empty it."""
    tokens = q.split()
    kept = [
        t for t in tokens if re.sub(r"[^a-z]", "", t.lower()) not in _ARXIV_STOPWORDS
    ]
    cleaned = " ".join(kept).strip()
    return cleaned or q


# --- L2: shared Redis cache (cross-pod dedup + normalized key + 429 stale) ---
# arXiv results are public, so the L2 key is tenant-less (unlike core/cache's
# tenant-scoped ``search:`` keys — hence the distinct ``arxiv:search:``
# namespace). The KEY-ONLY normalization below collapses near-duplicate
# phrasings; it does NOT change the query actually sent to arXiv.
_ARXIV_CACHE_KEY_STOPWORDS = _ARXIV_STOPWORDS | {"arxiv"}
_arxiv_redis_singleton: Any = None
_arxiv_redis_init_failed = False


async def _get_arxiv_redis() -> Any:
    """Return ONE shared async Redis client, created lazily and reused.

    ``get_redis_client()`` builds a fresh client + connection pool per call;
    caching a single client avoids leaking a pool on every arXiv search. Any
    failure (bad URL, no Redis) disables L2 for the process and the caller
    degrades to the L1 in-memory cache + a live arXiv call.
    """
    global _arxiv_redis_singleton, _arxiv_redis_init_failed
    if _arxiv_redis_singleton is not None:
        return _arxiv_redis_singleton
    if _arxiv_redis_init_failed:
        return None
    try:
        from src.services.core.cache import get_redis_client

        _arxiv_redis_singleton = await get_redis_client()
        return _arxiv_redis_singleton
    except Exception:
        _arxiv_redis_init_failed = True
        logger.debug("arXiv L2 Redis cache unavailable; using in-memory only")
        return None


def _normalize_cache_query(q: str) -> str:
    """Key-only query normalization (does NOT change what is sent to arXiv):
    lowercase, keep alnum/hyphen tokens, drop stopwords (incl 'arxiv'). Collapses
    'Search arXiv for recent papers on X.' and 'recent papers on X' to the same
    key so real + synthetic phrasings share one cache entry."""
    tokens = re.findall(r"[a-z0-9-]+", q.lower())
    kept = [t for t in tokens if t not in _ARXIV_CACHE_KEY_STOPWORDS]
    return " ".join(kept) or q.strip().lower()


def _arxiv_redis_key(
    query: str,
    max_results: int,
    categories: Optional[List[str]],
    recency_days: int,
    chronological: bool,
) -> str:
    import hashlib

    cats = ",".join(sorted(categories)) if categories else ""
    raw = "|".join(
        [
            _normalize_cache_query(query),
            str(int(max_results)),
            cats,
            str(int(recency_days)),
            str(int(bool(chronological))),
        ]
    )
    # usedforsecurity=False: this is a cache-key digest, not a security hash
    # (Bandit B324). Collision resistance is irrelevant for a cache bucket.
    digest = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()
    return _ARXIV_CACHE_REDIS_PREFIX + digest


async def _arxiv_redis_get(
    redis_key: str, allow_stale: bool
) -> Optional[Dict[str, Any]]:
    """Read the L2 entry. Fresh (age < FRESH_TTL) always; older entries only
    when ``allow_stale`` (the 429 fallback). None on any miss/Redis error."""
    import time

    client = await _get_arxiv_redis()
    if client is None:
        return None
    try:
        from src.services.core.cache import cache_get

        entry = await cache_get(client, redis_key)
    except Exception:
        return None
    if not isinstance(entry, dict) or "payload" not in entry:
        return None
    age = time.time() - float(entry.get("cached_at", 0) or 0)
    if not allow_stale and age > _ARXIV_CACHE_FRESH_TTL:
        return None
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else None


async def _arxiv_redis_set(redis_key: str, payload: Dict[str, Any]) -> None:
    """Store a successful payload with an embedded wall-clock ``cached_at`` and
    the longer STALE_TTL, so the 429 fallback can serve it past the fresh window."""
    import time

    client = await _get_arxiv_redis()
    if client is None:
        return
    try:
        from src.services.core.cache import cache_set

        await cache_set(
            client,
            redis_key,
            {"payload": payload, "cached_at": time.time()},
            ttl=_ARXIV_CACHE_STALE_TTL,
        )
    except Exception:
        logger.debug("Failed to write arXiv cache entry to Redis", exc_info=True)


async def _tool_search_arxiv(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search arXiv for papers."""
    from datetime import datetime, timedelta, timezone

    from src.services.arxiv.arxiv_service import ArXivIngestionService

    query = args.get("query", "")
    # Preserve the user's raw query for the cache key — the recency filter
    # below rewrites ``query`` with a minute-precision cutoff, which would
    # otherwise make two identical searches a minute apart miss the bounded
    # cache and defeat its 429-avoidance purpose (audit #14).
    original_query = query
    # Strip filler/recency words (e.g. "recent papers on") before the query
    # reaches arXiv's all-field index — they dilute relevance scores without
    # adding signal. The raw ``original_query`` is still used as the cache key.
    query = _sanitize_arxiv_query(query)
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

    # chronological=True: sort newest-first (useful for "what came out this
    # week"). Default false: rank by relevance so the best-matching papers
    # surface first regardless of date — the date FILTER above already bounds
    # the window; sorting by date inside a date-bounded window just re-orders
    # noise words and unrelated papers that happen to be recent.
    chronological = bool(args.get("chronological", False))
    sort_by = "submittedDate" if chronological else "relevance"

    # Key on the original query + recency_days (an int that already captures
    # the window), NOT the date-filtered query whose minute-precision cutoff
    # changes every minute. (audit #14)
    cache_key = _arxiv_cache_key(
        original_query, max_results, categories, recency_days, chronological
    )
    redis_key = _arxiv_redis_key(
        original_query, max_results, categories, recency_days, chronological
    )
    # Fresh lookup: L1 (per-process) then L2 (shared Redis). An L2 hit warms L1.
    cached = _arxiv_cache_get(cache_key)
    if cached is None:
        cached = await _arxiv_redis_get(redis_key, allow_stale=False)
        if cached is not None:
            _arxiv_cache_set(cache_key, cached)
    if cached is not None:
        return {**cached, "cached": True}

    try:
        async with ArXivIngestionService() as service:
            papers = await service.search_papers(
                query=query,
                max_results=max_results,
                categories=categories,
                sort_by=sort_by,
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
            payload = {
                "papers": results,
                "total": len(results),
                "query": query,
            }
            if not results:
                payload["warning"] = (
                    "No arXiv papers matched the query within the "
                    "recency window. Tell the user the search returned no "
                    "results — do not claim a search was performed without "
                    "naming that it was empty. Suggest broadening the "
                    "query, widening recency_days, or removing categories."
                )
            _arxiv_cache_set(cache_key, payload)
            await _arxiv_redis_set(redis_key, payload)
            return payload
    except Exception as e:
        logger.error("ArXiv search tool failed", exc_info=e)
        # On 429 or other failure, serve the last known result so the LLM can
        # proceed instead of looping: L1 any-age (bypasses the fresh check),
        # then L2 stale (entries live STALE_TTL past the fresh window).
        stale = _ARXIV_SEARCH_CACHE.get(cache_key)
        stale_payload = (
            stale[1]
            if stale is not None
            else await _arxiv_redis_get(redis_key, allow_stale=True)
        )
        if stale_payload is not None:
            return {
                **stale_payload,
                "cached": True,
                "stale": True,
                "warning": f"ArXiv unavailable ({e}); returned cached results.",
            }
        return {"error": f"ArXiv search failed: {str(e)}", "query": query}


async def _existing_document_id(
    db: AsyncSession, organization_id: Any, checksum: Optional[str]
) -> Optional[Any]:
    """Live document id for this org's copy of ``checksum``, if any.

    Mirrors the partial unique index ``uq_documents_org_checksum_live``
    (organization_id, checksum_sha256) WHERE NOT is_deleted — so the lookup
    matches exactly what the database would reject.
    """
    if not checksum:
        return None
    from sqlalchemy import select as _select

    stmt = (
        _select(Document.id)
        .where(
            Document.organization_id == organization_id,
            Document.checksum_sha256 == checksum,
            Document.is_deleted.is_(False),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _tool_ingest_arxiv(
    args: Dict[str, Any],
    user_id: str,
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Ingest arXiv papers into the RAG system by searching for them first, then ingesting."""
    from src.models.document import ProcessingStatus
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
                    failed_papers[pid] = "PDF download or content extraction failed"

            document_ids = []
            reused_document_ids: set = set()
            kb_sync_failed = False
            if ingested and current_user:
                # KEPT fresh sessions (audit B8 judgment): ingest is
                # deliberately phase-isolated — this atomic ``begin()`` batch
                # commits the documents independently of the KB dual-write
                # (kb_db) and the project link (link_db) below, so a failure
                # in a later phase can never roll back papers that already
                # landed. The tool-call session from execute_tool may carry
                # an open transaction, which ``begin()`` would reject.
                from src.core.database import AsyncSessionLocal

                promoted_storage: List[Dict[str, Any]] = []
                try:
                    persisted_documents: List[Document] = []
                    async with AsyncSessionLocal() as fresh_db:
                        async with fresh_db.begin():
                            for doc in ingested:
                                from src.services.arxiv.storage import store_arxiv_pdf

                                document_id = uuid4()
                                storage_fields = await asyncio.to_thread(
                                    store_arxiv_pdf,
                                    doc,
                                    current_user.organization_id,
                                    document_id,
                                )
                                promoted_storage.append(storage_fields)

                                # Content-hash dedup is a PARTIAL unique index
                                # (organization_id, checksum_sha256) over live
                                # rows. Re-ingesting a paper the org already
                                # has previously raised UniqueViolationError
                                # out of the atomic begin() block, so ONE
                                # duplicate destroyed the whole batch — nine
                                # new papers lost to the tenth being familiar.
                                # Reuse the existing row instead: the paper is
                                # in the library, which is what the user asked
                                # for, and the project link below still runs.
                                existing_id = await _existing_document_id(
                                    fresh_db,
                                    current_user.organization_id,
                                    storage_fields.get("checksum_sha256"),
                                )
                                if existing_id is not None:
                                    logger.info(
                                        "arxiv ingest: paper already in library "
                                        "(document %s), reusing",
                                        existing_id,
                                    )
                                    document_ids.append(str(existing_id))
                                    reused_document_ids.add(str(existing_id))
                                    continue

                                document = Document(
                                    id=document_id,
                                    title=getattr(doc, "title", "Untitled"),
                                    **storage_fields,
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

                            # Build search_vector so these COMPLETED docs are
                            # findable — without it the NULL tsvector never
                            # matches plainto_tsquery and the papers are
                            # invisible to doc search / RAG.
                            try:
                                from src.services.search.fulltext_search_service import (
                                    fulltext_search_service,
                                )

                                await fulltext_search_service.async_update_document_search_vectors(
                                    document_ids, fresh_db
                                )
                            except Exception as vec_err:  # noqa: BLE001
                                logger.warning(
                                    "arxiv ingest: search_vector update failed: %s",
                                    vec_err,
                                )
                            # begin() auto-commits on exit
                    # The rows now own these objects. Later failure-isolated KB
                    # or project work must never remove committed document data.
                    promoted_storage.clear()
                    logger.info(
                        "Ingested %d documents to DB: %s",
                        len(document_ids),
                        document_ids,
                    )

                    # Phase 2 dual-write: mirror into DO KB. Failure-isolated.
                    from src.core.config import settings as _kb_settings

                    if (
                        getattr(_kb_settings, "DO_KB_ENABLED", False)
                        and persisted_documents
                    ):
                        try:
                            from src.services.do_kb import sync_documents_to_kb

                            async with AsyncSessionLocal() as kb_db:
                                # AsyncSession.merge() IS a coroutine in SQLAlchemy
                                # 2.0 (inspect.iscoroutinefunction == True). Without
                                # await, `merged` held unawaited coroutine objects
                                # (RuntimeWarning) instead of Documents, the KB sync
                                # then AttributeError'd and was swallowed below — so
                                # the dual-write silently never ran. Await + commit so
                                # the do_kb_data_source_uuid writes actually persist.
                                merged = [
                                    await kb_db.merge(d) for d in persisted_documents
                                ]
                                await sync_documents_to_kb(kb_db, merged)
                                await kb_db.commit()
                        except Exception as kb_err:  # noqa: BLE001
                            kb_sync_failed = True
                            logger.warning(
                                "do_kb dual-write skipped for arxiv ingest: %s", kb_err
                            )
                except Exception as db_err:
                    from src.services.arxiv.storage import delete_arxiv_storage

                    for storage_fields in reversed(promoted_storage):
                        try:
                            await asyncio.to_thread(
                                delete_arxiv_storage, storage_fields
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "arxiv ingest rollback left an orphaned object: %s",
                                storage_fields.get("storage_path")
                                or storage_fields.get("file_path"),
                                exc_info=True,
                            )
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
                from src.core.database import AsyncSessionLocal as _LinkSession
                from src.services.agent.tool_helpers import _link_documents_to_project

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
                        "Failed to link ingested docs to project %s",
                        project_id,
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

            if reused_document_ids:
                n = len(reused_document_ids)
                message += (
                    f" {n} of these {'was' if n == 1 else 'were'} already in "
                    "your library; reused the existing copy."
                )

            if linked_project_name:
                message += f" Attached to project '{linked_project_name}'."

            # Promote link failure to a distinct status so the LLM doesn't
            # confuse "ingested fine but never attached" with full success.
            if link_error and status == INGEST_STATUS_COMPLETE:
                status = INGEST_STATUS_COMPLETE_LINK_FAILED

            # The KB dual-write is best-effort, but the agent must not imply the
            # papers reached the DO KB when it silently failed. Doc search still
            # works (search_vector is built above), so this is a note, not a
            # failure — surface it so the LLM stays honest.
            if kb_sync_failed and ingested_count > 0:
                message += (
                    " Note: knowledge-base sync did not complete, so these "
                    "papers are searchable via document search but may not yet "
                    "appear in knowledge-base retrieval."
                )

            failed_papers_list = [
                {"paper_id": pid, "reason": reason}
                for pid, reason in failed_papers.items()
            ]
            if failed_papers_list and ingested_count == 0:
                # Append per-paper failure detail so the LLM/user can see
                # exactly which IDs failed and why.
                reasons = ", ".join(
                    f"{fp['paper_id']} ({fp['reason']})" for fp in failed_papers_list
                )
                message += f" Details: {reasons}."

            result: Dict[str, Any] = {
                "status": status,
                "paper_ids": paper_ids,
                "document_ids": document_ids,
                "ingested_count": ingested_count,
                "requested_count": requested_count,
                "failed_papers": failed_papers_list,
                "project_id": linked_project_id,
                "project_name": linked_project_name,
                "link_error": link_error,
                "kb_sync_failed": kb_sync_failed,
                "message": message,
            }

            # A zero/partial ingest must reach the graph as a FAILURE. The tool
            # layer classifies on a top-level "error" key (_nodes_tools:
            # `if "error" in result`), so a payload that only carries
            # status="ingestion_failed" was recorded status="completed":
            # the error ceiling never tripped, tool_dedupe cached the failure
            # as a good result and short-circuited the retry, and
            # find_repeated_failures never saw it, so the circuit breaker was
            # bypassed too. A run that imported nothing was indistinguishable
            # from success in agent state.
            if status in _INGEST_FAILURE_STATUSES:
                result["error"] = message

            return result
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

        from src.services.agent._pii_redact import redact_pii

        return {
            "documents": [
                {
                    "id": str(d.id),
                    "title": redact_pii(d.title) if d.title else d.title,
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
    from src.services.do_kb.retrieval import (
        DOKBRetrieveStatus,
        resolve_org_kb_uuid,
        retrieve_kb_chunks,
    )

    kb_uuid: Optional[str] = None
    if db is not None:
        kb_uuid = await resolve_org_kb_uuid(db, current_user.organization_id)

    if not kb_uuid:
        return {
            "chunks": [],
            "total": 0,
            "source": "do_kb",
            "reason": "not_provisioned",
        }

    # Shared retrieve core (audit B2). This tool has no timeout and surfaces an
    # error dict on failure; the 404-vs-transient logging lives in the shared
    # helper. A non-DOKnowledgeBaseError propagates out of the helper and is
    # caught by the broad except below, preserving the tool's error-dict path.
    try:
        outcome = await retrieve_kb_chunks(
            kb_uuid=kb_uuid,
            query=query,
            org_id=current_user.organization_id,
            top_k=top_k,
        )
    except Exception as exc:
        logger.warning("do_kb_retrieve failed: %s", exc)
        return {
            "chunks": [],
            "total": 0,
            "source": "do_kb",
            "error": f"Retrieval failed: {exc}",
        }

    if outcome.status is not DOKBRetrieveStatus.SUCCESS:
        return {
            "chunks": [],
            "total": 0,
            "source": "do_kb",
            "error": f"Retrieval failed: {outcome.error}",
        }
    result = outcome.result

    # Resolve storage-key document_ids back to real Document rows and
    # optionally filter by project membership.
    project_id = args.get("project_id")
    # When the caller scopes to a project, verify they actually own it before
    # using it as a filter — otherwise passing another (in-org) project's id
    # would reveal which org documents belong to it (membership inference).
    # Mirrors the _verify_project_ownership guard the sibling project tools use.
    resolved_project_id: Optional[str] = None
    if project_id:
        if db is None:
            # Can't verify without a session — drop the filter rather than
            # trust an unverified id (fall back to org-wide scoping).
            project_id = None
        else:
            project = await _verify_project_ownership(project_id, db, current_user)
            if not project:
                return {
                    "chunks": [],
                    "total": 0,
                    "source": "do_kb",
                    "error": "Project not found or access denied",
                }
            resolved_project_id = str(project.id)

    title_by_key: dict[str, tuple[str, str]] = {}
    chunks_to_emit = result.chunks
    if db is not None and result.chunks:
        from src.services.do_kb.resolve import resolve_and_filter_chunks

        title_by_key, chunks_to_emit = await resolve_and_filter_chunks(
            chunks=result.chunks,
            org_id=current_user.organization_id,
            session=db,
            project_id=resolved_project_id,
        )

    from src.services.do_kb.postprocess import sanitize_and_deduplicate_chunks

    postprocessed = sanitize_and_deduplicate_chunks(chunks_to_emit)
    logger.info(
        "do_kb tool postprocess complete",
        extra={
            "input_count": postprocessed.input_count,
            "output_count": postprocessed.output_count,
            "duplicate_count": postprocessed.duplicate_count,
            "redacted_count": postprocessed.redacted_count,
        },
    )
    chunks_to_emit = postprocessed.chunks
    if not chunks_to_emit:
        return {
            "chunks": [],
            "total": 0,
            "source": "do_kb",
            "reason": "no_safe_chunks",
            "evidence_mode": False,
        }

    if chunks_to_emit and getattr(_kb_settings, "AGENT_DOKB_COHERE_RERANK", False):
        from src.services.do_kb.rerank import cohere_rescore_chunks

        chunks_to_emit = await cohere_rescore_chunks(query, chunks_to_emit)

    from src.services.agent._pii_redact import redact_pii

    chunks_payload = []
    for c in chunks_to_emit:
        resolved_id, title = title_by_key.get(c.document_id or "", (None, None))
        try:
            canonical_document_id = str(UUID(str(resolved_id))) if resolved_id else None
        except (ValueError, TypeError, AttributeError):
            canonical_document_id = None
        title_candidate = title or (c.metadata or {}).get("title")
        safe_title = redact_pii(title_candidate).strip() or "Untitled"
        chunks_payload.append(
            {
                "text": c.text,
                "score": c.score,
                "score_source": (c.metadata or {}).get("score_source"),
                "document_id": canonical_document_id,
                "title": safe_title,
                "metadata": c.metadata,
            }
        )

    evidence_mode = False
    if chunks_payload and getattr(_kb_settings, "AGENT_ITERATIVE_RETRIEVAL", False):
        from src.services.agent.evidence import summarize_evidence

        chunks_payload = await summarize_evidence(query, chunks_payload)
        evidence_mode = True

    return {
        "chunks": chunks_payload,
        "total": len(chunks_payload) if project_id else result.total,
        "source": "do_kb",
        "query": query,
        "evidence_mode": evidence_mode,
    }


async def _tool_add_document_to_project(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Add an existing document to a research project.

    ``db`` is the tool-call-scoped session opened by ``execute_tool`` —
    parallel add_document_to_project calls each own their session, so the
    former ad-hoc fresh-session dodge here is no longer needed (audit B8).
    """
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_id = args.get("document_id", "")
    project_id = args.get("project_id", "")

    if not document_id:
        return {"error": "document_id is required"}
    if not project_id:
        return {"error": "project_id is required"}

    try:
        # Resolve document (UUID or title)
        doc = await _resolve_document_id(document_id, db, current_user)
        if not doc:
            return {
                "error": f"Document '{document_id}' not found. The document must be ingested into the system first. "
                "Use ingest_arxiv_papers to ingest papers, then use the returned document_ids (UUIDs)."
            }
        doc_uuid = doc.id

        # Verify project ownership (resolves UUID or name)
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        from src.services.agent.tool_helpers import _link_documents_to_project

        result = await _link_documents_to_project(db, project, [str(doc_uuid)])
        await db.commit()

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
    if not db or not current_user:
        return {"error": "Authentication required"}

    name = (args.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}

    from src.services.research.project_service import ProjectService
    from src.shared.research_schemas import ProjectCreate

    try:
        # ``db`` is tool-call-scoped (execute_tool opens one session per
        # call), so the service can use it directly; ProjectService commits
        # internally. (audit B8 — former fresh-session dodge removed.)
        service = ProjectService(db)

        workspace_id_raw = args.get("workspace_id")
        if workspace_id_raw:
            try:
                workspace_id = UUID(str(workspace_id_raw))
            except ValueError:
                return {"error": "workspace_id must be a valid UUID"}
        else:
            workspace_ids = await service._get_workspace_ids_for_user(current_user.id)
            if not workspace_ids:
                return {
                    "error": ("No workspace found for user. Create a workspace first.")
                }
            workspace_id = workspace_ids[0]

        payload = ProjectCreate(
            workspace_id=workspace_id,
            name=name,
            description=args.get("description") or None,
            research_goals=args.get("research_goals") or None,
            tags=list(args.get("tags") or []),
            deadline=None,
            color=None,
            icon=None,
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

    from src.services.research.project_service import ProjectService

    try:
        # Verify project ownership (resolves UUID or name). Kept in the
        # adapter — the tool and the REST route authorize differently, so
        # ProjectService.create_note stays persistence-only. ``db`` is the
        # tool-call-scoped session (audit B8 — fresh-session dodge removed).
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        note = await ProjectService(db).create_note(
            user_id=current_user.id,
            project_id=project.id,
            title=title,
            content=content,
            tags=tags or [],
        )

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
    compact payload suitable for LLM context. ``db`` is the tool-call-scoped
    session opened by ``execute_tool`` (audit B8 — the former fresh-session
    dodge of the shared graph session is no longer needed).
    """
    if not db or not current_user:
        return {"error": "Authentication required"}

    raw_limit = args.get("limit", 20)
    try:
        limit = max(1, min(int(raw_limit), 50))
    except (TypeError, ValueError):
        limit = 20

    status = (args.get("status") or "").strip() or None
    tag = (args.get("tag") or "").strip() or None
    search = (args.get("search") or "").strip() or None

    from src.services.research.project_service import ProjectService

    try:
        service = ProjectService(db)
        result = await service.list_projects(
            user_id=current_user.id,
            project_status=status,
            tag=tag,
            search=search,
            skip=0,
            limit=limit,
        )

        projects = list(result.get("projects") or [])

        # A search that matches nothing must not look like "you have no
        # projects". Observed on dev: asked to "save it to my library", the
        # model called list_projects(search="library"), got [], then called
        # create_project_note with no project_id — a failed destructive call,
        # which costs a human confirmation round trip — before retrying
        # unfiltered and succeeding. The user's phrasing is rarely a project
        # name, so fall back to the unfiltered list and say the filter was
        # dropped, rather than reporting an empty library to someone who has
        # several.
        search_ignored = False
        if search and not projects:
            try:
                fallback = await service.list_projects(
                    user_id=current_user.id,
                    project_status=status,
                    # ``tag`` is dropped with ``search``: both are free text
                    # the model derives from the user's phrasing, and a
                    # hallucinated tag dead-ends exactly like a hallucinated
                    # name. ``status`` is kept — it is a constrained
                    # vocabulary and a plausible real intent ("my active
                    # projects").
                    tag=None,
                    search=None,
                    skip=0,
                    limit=limit,
                )
            except Exception:
                # The first query succeeded; a failure here must not turn a
                # usable empty result into an error the model has to handle.
                logger.warning("list_projects search fallback failed", exc_info=True)
            else:
                fallback_projects = list(fallback.get("projects") or [])
                if fallback_projects:
                    projects = fallback_projects
                    result = fallback
                    search_ignored = True

        payload: Dict[str, Any] = {
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
        if search_ignored:
            shown = len(projects)
            total = result.get("total", shown)
            payload["search_ignored"] = search
            # State the fact; withhold the licence. The model has just shown
            # it does not know the target's name, and the confirmation card
            # renders only {name, args} — the user approving a write sees a
            # project_id UUID, never a project name, so a wrong pick is not
            # human-catchable. Telling it to "pick the best fit" would trade a
            # visible failed call for a silent write into the wrong project.
            #
            # "every project" would also be false whenever total > limit:
            # total is an unlimited count, the rows are limited.
            payload["note"] = (
                f"No project name matched '{search}'. The filter was dropped; "
                f"showing {shown} of {total} projects. If exactly one is an "
                "obvious fit, use it; otherwise ask the user which one before "
                "writing."
            )
        return payload
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
                        'library. Use ingest_arxiv_papers(["'
                        f'{document_id}"]) first, then retry summarize_document '
                        "with the returned internal document_id."
                    ),
                    "error_type": "recoverable",
                    "suggestion": "ingest_arxiv_papers",
                }

            # The id may be a *project* id, not a document id — a common
            # agent mistake (reusing a project_id from list_projects; trace
            # 019f4386). Steer it to resolve real document ids first. Wrapped
            # so any lookup failure falls through to the generic error.
            try:
                project = await _verify_project_ownership(document_id, db, current_user)
            except Exception:
                project = None
            if project:
                return {
                    "error": (
                        f"'{document_id}' is a project id, not a document id. "
                        f'Call list_project_documents(project_id="{document_id}") '
                        f'to get the document_ids in the "{project.name or "project"}" '
                        "project, then call summarize_document with one of those ids."
                    ),
                    "error_type": "recoverable",
                    "suggestion": "list_project_documents",
                }
            return {"error": "Document not found or access denied"}

        # Use existing content_text if available, else extract
        text = doc.content_text or ""
        if not text:
            from src.services.documents.file_service import FileService

            file_service = FileService(db)
            # Offload blocking PDF/CSV/Excel parsing off the event loop.
            text = await asyncio.to_thread(file_service.extract_text_content, doc)

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
        except Exception as llm_exc:
            # Don't dress raw truncated text up as an LLM summary — same
            # reasoning as compare_documents: success-shaped fallback makes
            # the agent present a non-summary as a real one.
            logger.warning("summarize_document LLM call failed", exc_info=llm_exc)
            return {
                "error": "Document summary could not be generated due to a model error. Please retry."
            }

        return {
            "summary": summary,
            "word_count": word_count,
            "title": doc.title or "Untitled",
            "document_id": str(doc.id),
        }
    except Exception as e:
        logger.error("summarize_document tool failed", exc_info=e)
        return {"error": f"Summarization failed: {str(e)}"}


#: Per-document character budget sent to the comparison model.
_COMPARE_DOCUMENTS_TEXT_LIMIT = 4000


def _compare_documents_system_prompt(comparison_type: str) -> str:
    """Grounding contract for the comparison model.

    Without the second paragraph the model answers from subject-matter
    knowledge rather than the supplied text: the agent-writing-flow-v1
    benchmark caught it asserting GNN oversmoothing, difficulty with
    long-range molecular interactions, and benchmark/dataset discussion that
    appear in neither compared document, which fails the grounding rubric on
    every trial. Document text is truncated, so the model is also told not to
    read absence as evidence.
    """
    return (
        "You are a research assistant. Compare the following documents "
        f"({comparison_type} comparison). Identify similarities, differences, "
        "and key themes across them. Be structured and concise.\n\n"
        "Ground every statement in the supplied document text. Do not "
        "introduce facts, limitations, benchmarks, metrics, or technical "
        "claims that the text does not state, and do not draw on outside "
        "knowledge of the subject matter however well established it is. "
        "Attribute each point to the document that supports it, and never "
        "attribute a point to a document that does not state it. Where the "
        "supplied text is too thin to support a comparison, say the text does "
        "not cover it rather than filling the gap. The text is truncated to "
        f"{_COMPARE_DOCUMENTS_TEXT_LIMIT} characters per document, so treat a "
        "missing detail as unknown, not as absent from the source."
    )


async def _tool_compare_documents(
    args: Dict[str, Any],
    db: Optional[AsyncSession],
    current_user: Optional[User],
) -> Dict[str, Any]:
    """Compare multiple documents using text extraction + LLM."""
    if not db or not current_user:
        return {"error": "Authentication required"}

    document_ids = args.get("document_ids", [])
    _COMPARISON_TYPES = {"general", "methodology", "findings", "themes"}
    comparison_type = args.get("type", "general")
    if comparison_type not in _COMPARISON_TYPES:
        comparison_type = "general"
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
                # Offload blocking PDF/CSV/Excel parsing off the event loop.
                text = await asyncio.to_thread(file_service.extract_text_content, doc)

            doc_texts.append(
                {
                    "id": str(doc.id),
                    "title": doc.title or "Untitled",
                    "text": text[:_COMPARE_DOCUMENTS_TEXT_LIMIT],
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
                        content=_compare_documents_system_prompt(comparison_type)
                    ),
                    HumanMessage(content=docs_content),
                ]
            )
            comparison = response.content
        except Exception as llm_exc:
            # Don't fabricate a successful comparison when the LLM call failed —
            # returning success-shaped text ("retrieved successfully") makes the
            # agent present a non-comparison as a real one. Surface an error so
            # the agent can retry or tell the user it couldn't compare.
            logger.warning("compare_documents LLM call failed", exc_info=llm_exc)
            return {
                "error": "Document comparison could not be generated due to a model error. Please retry."
            }

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
            # Offload blocking PDF/CSV/Excel parsing off the event loop.
            text = await asyncio.to_thread(file_service.extract_text_content, doc)

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


async def _tool_search_knowledge_graph(
    args: Dict[str, Any],
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Search the knowledge graph for entities."""
    if current_user is None or current_user.organization_id is None:
        return {"error": "Authentication required"}

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

        org_id = str(current_user.organization_id)
        loop = asyncio.get_running_loop()
        entities = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.search_entities(
                    query=query,
                    entity_types=type_filters,
                    limit=limit,
                    organization_id=org_id,
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


async def _tool_explore_entity_neighborhood(
    args: Dict[str, Any],
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Explore an entity's neighborhood — connected entities and relationships."""
    if current_user is None or current_user.organization_id is None:
        return {"error": "Authentication required"}

    entity_id = args.get("entity_id", "")
    max_depth = min(args.get("max_depth", 2), 3)
    limit = min(args.get("limit", 30), 50)

    if not entity_id:
        return {"error": "entity_id is required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        org_id = str(current_user.organization_id)
        loop = asyncio.get_running_loop()
        neighborhood = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.get_neighborhood(
                    entity_id=entity_id,
                    max_depth=max_depth,
                    limit=limit,
                    organization_id=org_id,
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


async def _tool_find_entity_paths(
    args: Dict[str, Any],
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Find relationship paths between two entities."""
    if current_user is None or current_user.organization_id is None:
        return {"error": "Authentication required"}

    source_id = args.get("source_entity_id", "")
    target_id = args.get("target_entity_id", "")
    max_depth = min(args.get("max_depth", 3), 5)

    if not source_id or not target_id:
        return {"error": "source_entity_id and target_entity_id are required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        org_id = str(current_user.organization_id)
        loop = asyncio.get_running_loop()
        paths = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.find_paths(
                    source_id=source_id,
                    target_id=target_id,
                    max_depth=max_depth,
                    organization_id=org_id,
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


async def _tool_get_graph_stats(
    args: Dict[str, Any],
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Get knowledge graph statistics."""
    if current_user is None or current_user.organization_id is None:
        return {"error": "Authentication required"}

    try:
        from src.services.knowledge_graph.knowledge_graph_service import (
            knowledge_graph_service,
        )

        org_id = str(current_user.organization_id)
        loop = asyncio.get_running_loop()
        analytics = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: knowledge_graph_service.get_graph_analytics(
                    organization_id=org_id,
                ),
            ),
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
    _DRAFT_STYLES = {"academic", "technical", "summary"}
    style = args.get("style", "academic")
    if style not in _DRAFT_STYLES:
        style = "academic"

    if not project_id:
        return {"error": "project_id is required"}
    if not themes:
        return {"error": "At least one theme is required"}

    try:
        project = await _verify_project_ownership(project_id, db, current_user)
        if not project:
            return {"error": "Project not found or access denied"}

        from src.services.research.draft_generation_service import (
            DraftGenerationService,
        )

        # Background generation owns its own AsyncSessionLocal; the
        # request session here is only used for the ownership check above.
        draft_service = DraftGenerationService(db)
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
    elif result.exit_code != 0:
        # A non-zero exit with no structured error must still carry an
        # "error" key — the tool node's classify_error_from_payload keys
        # off it, and without one a failed run is reported to the LLM as
        # success.
        response["error"] = (
            result.stderr.strip() or f"Code exited with status {result.exit_code}"
        )

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
            if isinstance(result, BaseException):
                logger.warning(
                    "connector_search_failed: connector=%s error=%s",
                    connector.info.name,
                    str(result),
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

    from src.services.agent.memory import delete_memory_by_query, get_memory_store

    store = await get_memory_store()
    if store is None:
        return {"error": "forget_memory: memory store unavailable"}

    result = await delete_memory_by_query(store, user_id=user_id, query=query, limit=5)
    return {
        "status": "completed",
        "deleted": result["deleted"],
        "matches": result["matches"],
    }
