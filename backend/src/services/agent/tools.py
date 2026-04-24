"""LangGraph tool wrappers for agent tools.

Each tool delegates to the existing implementation in
``src.api.agent.execute`` and extracts ``db`` / ``current_user`` /
``page_context`` from the LangGraph ``RunnableConfig.configurable`` dict.
"""

import functools
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import tool
except Exception:  # pragma: no cover - exercised in tests via module stubs
    class _FallbackTool:
        """Small StructuredTool-like wrapper for test environments."""

        def __init__(self, fn):
            functools.update_wrapper(self, fn)
            self.func = fn
            self.coroutine = fn
            self.name = fn.__name__
            self.description = (fn.__doc__ or "").strip()

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    def tool(func=None, **_kwargs):
        def decorator(fn):
            return _FallbackTool(fn)

        if func is None:
            return decorator
        return decorator(func)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_context(
    config: RunnableConfig,
) -> Tuple[Optional[AsyncSession], Optional[User], dict]:
    """Extract db session, current user, and page context from config."""
    configurable = config.get("configurable", {})
    return (
        configurable.get("db"),
        configurable.get("current_user"),
        configurable.get("page_context", {}),
    )


def _resolve_project_id(
    explicit_project_id: Optional[str],
    page_context: dict,
) -> Optional[str]:
    """Return *explicit_project_id* if given, else fall back to page context."""
    if explicit_project_id:
        return explicit_project_id
    if page_context.get("type") == "project" and page_context.get("project_id"):
        return page_context["project_id"]
    return None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@tool
async def search_arxiv(
    query: str,
    max_results: int = 5,
    categories: Optional[List[str]] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Search arXiv for academic papers.

    Use when the user asks to find, search, or look up research papers,
    academic publications, or scientific articles.
    """
    config = config or {}
    from src.api.agent.execute import _tool_search_arxiv

    args: Dict[str, Any] = {"query": query, "max_results": max_results}
    if categories:
        args["categories"] = categories
    return await _tool_search_arxiv(args)


@tool
async def ingest_arxiv_papers(
    paper_ids: List[str],
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Ingest arXiv papers into the RAG system for indexing and search.

    Use when the user wants to add, import, download, or ingest specific arXiv
    papers. Requires paper IDs (e.g., '2401.12345').
    """
    config = config or {}
    from src.api.agent.execute import _tool_ingest_arxiv

    db, current_user, _page_ctx = _get_context(config)
    user_id = str(current_user.id) if current_user else ""
    return await _tool_ingest_arxiv(
        {"paper_ids": paper_ids}, user_id, db, current_user
    )


@tool
async def search_documents(
    query: str,
    max_results: int = 10,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Search the user's indexed documents by title or content."""
    config = config or {}
    from src.api.agent.execute import _tool_search_documents

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_search_documents(
        {"query": query, "max_results": max_results}, db, current_user
    )


@tool
async def add_document_to_project(
    document_id: str,
    project_id: Optional[str] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Add an existing document to a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
    config = config or {}
    from src.api.agent.execute import _tool_add_document_to_project

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    return await _tool_add_document_to_project(
        {"document_id": document_id, "project_id": resolved_pid or ""},
        db,
        current_user,
    )


@tool
async def create_project(
    name: str,
    description: Optional[str] = None,
    research_goals: Optional[str] = None,
    tags: Optional[List[str]] = None,
    workspace_id: Optional[str] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Create a new research project (folder) for organizing papers, documents, and notes.

    If *workspace_id* is omitted, the user's first workspace is used.
    """
    config = config or {}
    from src.api.agent.execute import _tool_create_project

    db, current_user, _ = _get_context(config)
    args: Dict[str, Any] = {"name": name}
    if description:
        args["description"] = description
    if research_goals:
        args["research_goals"] = research_goals
    if tags:
        args["tags"] = tags
    if workspace_id:
        args["workspace_id"] = workspace_id
    return await _tool_create_project(args, db, current_user)


@tool
async def create_project_note(
    title: str,
    content: str,
    project_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Create a markdown note in a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
    config = config or {}
    from src.api.agent.execute import _tool_create_project_note

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    args: Dict[str, Any] = {
        "title": title,
        "content": content,
        "project_id": resolved_pid or "",
    }
    if tags:
        args["tags"] = tags
    return await _tool_create_project_note(args, db, current_user)


@tool
async def list_projects(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """List the user's research projects.

    Use when the user asks "what projects do I have", "list my projects",
    or wants to discover existing projects before choosing one. Prefer this
    over asking the user to provide a project_id.
    """
    config = config or {}
    from src.api.agent.execute import _tool_list_projects

    db, current_user, _page_ctx = _get_context(config)
    args: Dict[str, Any] = {"limit": limit}
    if status:
        args["status"] = status
    if tag:
        args["tag"] = tag
    if search:
        args["search"] = search
    return await _tool_list_projects(args, db, current_user)


@tool
async def list_project_documents(
    project_id: Optional[str] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """List all documents in a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
    config = config or {}
    from src.api.agent.execute import _tool_list_project_documents

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    return await _tool_list_project_documents(
        {"project_id": resolved_pid or ""}, db, current_user
    )


@tool
async def summarize_document(
    document_id: str,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Summarize a document's content.

    Use when the user asks for a summary or overview of a specific document.
    """
    config = config or {}
    from src.api.agent.execute import _tool_summarize_document

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_summarize_document(
        {"document_id": document_id}, db, current_user
    )


@tool
async def compare_documents(
    document_ids: List[str],
    type: str = "general",
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Compare multiple documents to find similarities, differences, and shared themes.

    Use when the user wants to compare, contrast, or analyze differences
    between two or more documents.
    """
    config = config or {}
    from src.api.agent.execute import _tool_compare_documents

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_compare_documents(
        {"document_ids": document_ids, "type": type}, db, current_user
    )


@tool
async def extract_entities(
    document_id: str,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Extract named entities (people, organizations, concepts, etc.) from a document.

    Use when the user wants to identify key entities, people, organizations,
    or concepts mentioned in a document.
    """
    config = config or {}
    from src.api.agent.execute import _tool_extract_entities

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_extract_entities(
        {"document_id": document_id}, db, current_user
    )


@tool
async def search_knowledge_graph(
    query: str,
    entity_types: Optional[List[str]] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Search the knowledge graph for entities and their relationships.

    Use when the user asks about concepts, people, or organizations
    in the research corpus, or wants to explore entity relationships.
    """
    config = config or {}
    from src.api.agent.execute import _tool_search_knowledge_graph

    args: Dict[str, Any] = {"query": query}
    if entity_types:
        args["entity_types"] = entity_types
    return await _tool_search_knowledge_graph(args)


@tool
async def explore_entity_neighborhood(
    entity_id: str,
    max_depth: int = 2,
    limit: int = 30,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Explore an entity's neighborhood in the knowledge graph.

    Find all connected entities and the relationships between them.
    Use when the user asks "what is connected to X", "show me everything
    related to X", or wants to understand how an entity fits in the graph.
    First use search_knowledge_graph to find the entity_id.
    """
    config = config or {}
    from src.api.agent.execute import _tool_explore_entity_neighborhood

    return await _tool_explore_entity_neighborhood(
        {"entity_id": entity_id, "max_depth": max_depth, "limit": limit}
    )


@tool
async def find_entity_paths(
    source_entity_id: str,
    target_entity_id: str,
    max_depth: int = 3,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Find relationship paths between two entities in the knowledge graph.

    Use when the user asks "how is X related to Y", "what connects X and Y",
    or wants to understand the chain of relationships between two concepts.
    First use search_knowledge_graph to find both entity IDs.
    """
    config = config or {}
    from src.api.agent.execute import _tool_find_entity_paths

    return await _tool_find_entity_paths(
        {"source_entity_id": source_entity_id, "target_entity_id": target_entity_id, "max_depth": max_depth}
    )


@tool
async def get_graph_stats(
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Get statistics about the knowledge graph.

    Returns total entities, relationships, type distributions, and
    connectivity metrics. Use when the user asks about the size or shape
    of the knowledge base, or wants an overview of what's in the graph.
    """
    config = config or {}
    from src.api.agent.execute import _tool_get_graph_stats

    return await _tool_get_graph_stats({})


@tool
async def create_draft(
    themes: List[str],
    project_id: Optional[str] = None,
    style: str = "academic",
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Generate a literature review draft for a project based on themes.

    Use when the user wants to create a draft, write a review, or synthesize
    research around specific themes.
    """
    config = config or {}
    from src.api.agent.execute import _tool_create_draft

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    return await _tool_create_draft(
        {"project_id": resolved_pid or "", "themes": themes, "style": style},
        db,
        current_user,
    )


@tool
async def export_bibliography(
    document_ids: List[str],
    format: str = "bibtex",
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Export bibliography/references for documents in a specific citation format.

    Use when the user wants to export citations, references, or a bibliography
    for one or more documents. Supports bibtex, apa, ieee, and mla formats.
    """
    config = config or {}
    from src.api.agent.execute import _tool_export_bibliography

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_export_bibliography(
        {"document_ids": document_ids, "format": format}, db, current_user
    )


# ---------------------------------------------------------------------------
# Code Execution
# ---------------------------------------------------------------------------


@tool
async def execute_code(
    code: str,
    description: str,
    language: str = "python",
    packages: Optional[List[str]] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Execute Python code in a sandboxed E2B environment.

    Use this tool when the user asks you to run code, perform data analysis,
    create visualizations, train models, or do any computation that requires
    executing Python. The sandbox has numpy, pandas, matplotlib, scipy,
    scikit-learn, and seaborn pre-installed. You can install additional
    packages via the ``packages`` parameter.

    The sandbox is stateful within a conversation — variables and files
    persist between executions, so you can build on previous results.
    """
    config = config or {}
    from src.api.agent.execute import _tool_execute_code

    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    current_user = configurable.get("current_user")

    return await _tool_execute_code(
        {
            "code": code,
            "description": description,
            "language": language,
            "packages": packages,
        },
        thread_id=thread_id,
        current_user=current_user,
    )


# ---------------------------------------------------------------------------
# External database connectors
# ---------------------------------------------------------------------------


@tool
async def search_external_database(
    query: str,
    connector: Optional[str] = None,
    domain: Optional[str] = None,
    max_results: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Search external databases (PubMed, UniProt, ChEMBL, PubChem, FRED, SEC EDGAR, etc.).

    Provides a single entry point to 250+ external scientific and financial
    data sources. Supply ``connector`` to target one (e.g. ``"pubmed"``),
    ``domain`` to fan out across a category (``biomedical``, ``chemistry``,
    ``finance``, ``clinical``, ``genomics``, ``economic``, ``literature``),
    or omit both to search every available connector concurrently.

    Use when the user asks for proteins, compounds, mutations, clinical trials,
    economic time series, SEC filings, or any other domain-specific data not
    available in the local document store.
    """
    config = config or {}
    from src.api.agent.execute import _tool_search_external_database

    args: Dict[str, Any] = {"query": query, "max_results": max_results}
    if connector:
        args["connector"] = connector
    if domain:
        args["domain"] = domain
    if filters:
        args["filters"] = filters
    return await _tool_search_external_database(args)


@tool
async def list_external_databases(
    domain: Optional[str] = None,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """List the external database connectors available to the agent.

    Use when the user asks "what databases can you search", or before invoking
    ``search_external_database`` to discover the right connector name. Pass
    ``domain`` to filter by category.
    """
    config = config or {}
    from src.api.agent.execute import _tool_list_external_databases

    args: Dict[str, Any] = {}
    if domain:
        args["domain"] = domain
    return await _tool_list_external_databases(args)


# ---------------------------------------------------------------------------
# Exported list
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    create_project,
    list_projects,
    add_document_to_project,
    create_project_note,
    list_project_documents,
    summarize_document,
    compare_documents,
    extract_entities,
    search_knowledge_graph,
    create_draft,
    export_bibliography,
    execute_code,
    search_external_database,
    list_external_databases,
]
