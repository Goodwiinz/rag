"""LangGraph tool wrappers for agent tools.

Each tool delegates to the existing implementation in
``src.api.agent.execute`` and extracts ``db`` / ``current_user`` /
``page_context`` from the LangGraph ``RunnableConfig.configurable`` dict.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User

logger = logging.getLogger(__name__)


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
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """Search arXiv for academic papers.

    Use when the user asks to find, search, or look up research papers,
    academic publications, or scientific articles.
    """
    from src.api.agent.execute import _tool_search_arxiv

    args: Dict[str, Any] = {"query": query, "max_results": max_results}
    if categories:
        args["categories"] = categories
    return await _tool_search_arxiv(args)


@tool
async def ingest_arxiv_papers(
    paper_ids: List[str],
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """Ingest arXiv papers into the RAG system for indexing and search.

    Use when the user wants to add, import, download, or ingest specific arXiv
    papers. Requires paper IDs (e.g., '2401.12345').
    """
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
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """Search the user's indexed documents by title or content."""
    from src.api.agent.execute import _tool_search_documents

    db, current_user, _page_ctx = _get_context(config)
    return await _tool_search_documents(
        {"query": query, "max_results": max_results}, db, current_user
    )


@tool
async def add_document_to_project(
    document_id: str,
    project_id: Optional[str] = None,
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """Add an existing document to a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
    from src.api.agent.execute import _tool_add_document_to_project

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    return await _tool_add_document_to_project(
        {"document_id": document_id, "project_id": resolved_pid or ""},
        db,
        current_user,
    )


@tool
async def create_project_note(
    title: str,
    content: str,
    project_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """Create a markdown note in a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
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
async def list_project_documents(
    project_id: Optional[str] = None,
    config: RunnableConfig = {},  # noqa: B006
) -> Dict[str, Any]:
    """List all documents in a research project.

    If *project_id* is omitted and the user is on a project page, the
    project is inferred from the page context.
    """
    from src.api.agent.execute import _tool_list_project_documents

    db, current_user, page_ctx = _get_context(config)
    resolved_pid = _resolve_project_id(project_id, page_ctx)
    return await _tool_list_project_documents(
        {"project_id": resolved_pid or ""}, db, current_user
    )


# ---------------------------------------------------------------------------
# Exported list
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    search_arxiv,
    ingest_arxiv_papers,
    search_documents,
    add_document_to_project,
    create_project_note,
    list_project_documents,
]
