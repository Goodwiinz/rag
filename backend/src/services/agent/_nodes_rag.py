"""RAG node + DO KB / hybrid search helpers for the agent graph.

Extracted from ``graph.py`` so the orchestration module stays under the
800-line house rule. ``graph.py`` re-exports ``rag_node`` so the
LangGraph builder + existing tests keep working without rewriting any
import.

Two stages of retrieval policy live here:

* **Conversational fast-path** — ``_is_retrieval_query`` rejects greetings
  / acks / one-word messages so we don't burn an embedding round-trip
  + ~935 retrieval tokens on every "hi". Trace 019e168a documented the
  cost of leaving the fast-path off.
* **Primary read (DO KB) + fallback** — ``_try_primary_do_kb_read`` runs
  the DigitalOcean Knowledge Base when the org has one configured and
  the active project is known; ``_legacy_hybrid_search_fallback`` is
  the Qdrant + reranker chain used when DO KB is disabled or returns
  nothing.

This module reaches back into ``graph.py`` for the shared helper
``_extract_project_id_from_text`` via a lazy import to avoid a cycle.
Document resolution / project-scope filtering is delegated to
``src.services.do_kb.resolve.resolve_and_filter_chunks``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.services.agent.observability import track_node_execution
from src.services.agent.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversational fast-path heuristics
# ---------------------------------------------------------------------------

# Verbs / phrases that strongly imply the user wants document retrieval. Kept as
# a frozenset to make membership checks O(1) and the literal hard to mutate.
_RETRIEVAL_VERBS: frozenset[str] = frozenset(
    {
        "find",
        "search",
        "show",
        "list",
        "lookup",
        "summarize",
        "compare",
        "explore",
        "ingest",
        "what is",
        "tell me about",
    }
)

# Tool-name prefixes — if the user pasted/typed something like ``list_projects``
# or ``search_arxiv`` we should treat that as a retrieval-style query and skip
# the heuristic shortcut.
_TOOL_NAME_PREFIXES: tuple[str, ...] = (
    "search_",
    "list_",
    "summarize_",
    "compare_",
    "explore_",
    "extract_",
    "ingest_",
)

# Conversational patterns that never need document retrieval. Checked before
# retrieval-verb detection so "thanks" doesn't accidentally match "search".
_CONVERSATIONAL_PATTERNS: frozenset[str] = frozenset(
    {
        "what model",
        "which model",
        "how are you",
        "thank",
        "thanks",
        "ok",
        "okay",
        "yes",
        "no",
        "got it",
        "cool",
        "nice",
        "good",
        "great",
        "bye",
        "goodbye",
        "see you",
        "hello",
        "hey",
        "hi",
    }
)

# Length threshold (in whitespace-delimited tokens) below which a query is
# considered "short". Short queries without a retrieval verb skip RAG.
_SHORT_QUERY_TOKEN_LIMIT: int = 8


def _resolve_active_project_id(
    existing_project_id: Optional[str], extracted_pid: Optional[str]
) -> Optional[str]:
    """Resolve which project RAG retrieval should be scoped to.

    The active context (``state.current_project_id`` / ``page_context``) takes
    precedence over a UUID parsed from the user's message text, so a stale or
    quoted ``/projects/<uuid>`` URL cannot silently re-scope retrieval to
    another project (cross-project exposure). Text extraction only wins when no
    project context is active yet. (Audit #7.)
    """
    return existing_project_id or extracted_pid or None


def _is_retrieval_query(content: str) -> bool:
    """Return ``True`` when *content* looks like it needs document retrieval.

    Used by :func:`rag_node` to skip the (expensive) hybrid search whenever the
    latest user message is clearly conversational — e.g. ``"hi"``, ``"thanks!"``
    or a one-word ack. The heuristic is intentionally conservative: any
    long-ish message OR any message containing a retrieval verb / tool-name
    prefix is treated as retrieval to avoid degrading recall.

    Rules (a query is treated as NON-retrieval when ANY of these hold):
      0. lowercased content matches a ``_CONVERSATIONAL_PATTERNS`` entry

    Otherwise treated as retrieval when ANY of these hold:
      1. token count >= ``_SHORT_QUERY_TOKEN_LIMIT`` (8)
      2. lowercased content contains any ``_RETRIEVAL_VERBS`` substring
      3. lowercased content starts with any ``_TOOL_NAME_PREFIXES`` prefix
    """
    if not content or not content.strip():
        return False

    lowered = content.lower().strip()
    tokens = content.split()

    for pattern in _CONVERSATIONAL_PATTERNS:
        if re.search(r"\b" + re.escape(pattern) + r"\b", lowered):
            return False

    if len(tokens) >= _SHORT_QUERY_TOKEN_LIMIT:
        return True

    for prefix in _TOOL_NAME_PREFIXES:
        if lowered.startswith(prefix):
            return True

    for verb in _RETRIEVAL_VERBS:
        if verb in lowered:
            return True

    return False


# ---------------------------------------------------------------------------
# DO KB primary read (Phase 4b) + Qdrant fallback
# ---------------------------------------------------------------------------


def _shape_do_kb_context(chunk, title_by_key: dict[str, tuple[str, str]]) -> dict:
    """Map a DO KB chunk into the rag_node context envelope.

    Resolves the chunk's storage-key ``document_id`` back to the canonical
    ``Document.id`` (UUID) + ``Document.title`` so citations render with real
    titles instead of "DO KB chunk".
    """
    storage_key = chunk.document_id
    resolved_id, title = title_by_key.get(storage_key, (None, None))
    return {
        "document_id": resolved_id or storage_key,
        "title": title or (chunk.metadata or {}).get("title") or storage_key or "Untitled",
        "content": chunk.text[:3000],
        "score": float(chunk.score),
    }


try:
    from langsmith import traceable as _ls_traceable
except Exception:  # noqa: BLE001 - langsmith optional at runtime
    _ls_traceable = None


def _maybe_traced_retriever(name: str):
    """Return a langsmith traceable decorator with run_type=retriever, or no-op."""
    if _ls_traceable is None:
        def _identity(fn):
            return fn

        return _identity
    return _ls_traceable(run_type="retriever", name=name)


@_maybe_traced_retriever("do_kb_retriever")
async def _try_primary_do_kb_read(
    query: str,
    current_user,
    project_id: Optional[str] = None,
) -> Optional[List[dict]]:
    """Phase 4b: return DO KB chunks shaped like rag_node contexts.

    Returns None when primary read is disabled, the org has no KB, or the
    call fails — caller then falls back to the legacy Qdrant path.

    When *project_id* is provided, post-filters chunks so only documents
    that belong to the active project survive. DO KB itself is org-scoped,
    so cross-project leakage (chunks from sibling projects) is filtered
    via the ``collection_documents`` association table.
    """
    try:
        from src.core.config import settings as _kb_cfg

        if not getattr(_kb_cfg, "DO_KB_PRIMARY_READ", False):
            return None
        org_id = getattr(current_user, "organization_id", None)
        if not org_id:
            return None

        from src.core.database import AsyncSessionLocal
        from src.models.organization import Organization
        from src.services.do_kb import get_do_kb_client

        async with AsyncSessionLocal() as session:
            org = await session.get(Organization, org_id)
            kb_uuid = getattr(org, "do_kb_uuid", None) if org else None
            if not kb_uuid:
                return None

            client = get_do_kb_client()
            result = await client.retrieve(kb_uuid=kb_uuid, query=query)
            if not result.chunks:
                return None

            from src.services.do_kb.resolve import resolve_and_filter_chunks

            title_by_key, chunks_to_emit = await resolve_and_filter_chunks(
                chunks=result.chunks,
                org_id=org_id,
                session=session,
                project_id=project_id,
            )

            # Two distinct empty-result paths that trigger Qdrant fallback:
            if project_id and not title_by_key and result.chunks:
                logger.info(
                    "do_kb_read: %d chunks unresolvable to org documents under "
                    "project scope %s — returning None to trigger fallback",
                    len(result.chunks),
                    project_id,
                )
                return None
            if project_id and title_by_key and not chunks_to_emit:
                logger.info(
                    "do_kb_read: all %d chunks filtered out by project scope %s",
                    len(result.chunks),
                    project_id,
                )
                return None

        return [
            _shape_do_kb_context(c, title_by_key) for c in chunks_to_emit
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("do_kb primary read failed, falling back: %s", exc)
        return None


@_maybe_traced_retriever("hybrid_search_retriever")
async def _legacy_hybrid_search_fallback(
    query: str, current_user
) -> List[dict]:
    """Fallback to hybrid search when DO KB is unavailable or returns nothing."""
    try:
        from src.models.search_schemas import SearchQuery, SearchSortOrder, SearchType
        from src.services.search.hybrid_search_service import hybrid_search_service

        search_request = SearchQuery(
            query=query,
            limit=5,
            search_type=SearchType.HYBRID,
            sort_order=SearchSortOrder.RELEVANCE,
            filters=None,
        )
        org_id = (
            str(current_user.organization_id)
            if current_user.organization_id
            else None
        )
        uid = str(current_user.id)
        search_response = await asyncio.wait_for(
            asyncio.to_thread(
                hybrid_search_service.search,
                search_request=search_request,
                user_id=uid,
                organization_id=org_id,
            ),
            timeout=15.0,
        )
        contexts: List[dict] = []
        for i, result in enumerate(search_response.results[:5]):
            doc_id = getattr(result, "document_id", None)
            title = getattr(result, "title", "Untitled") or f"Document {i + 1}"
            metadata = getattr(result, "metadata", {}) or {}
            content = metadata.get("full_text") or metadata.get("text", "")
            if not content:
                content = getattr(result, "content_preview", None) or ""
            score = getattr(result, "relevance_score", 0.0)
            contexts.append({
                "document_id": str(doc_id) if doc_id else None,
                "title": title,
                "content": content[:3000],
                "score": float(score),
            })
        return contexts
    except Exception as exc:
        logger.warning("hybrid search fallback failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

# Leading imperative tokens that add no retrieval signal ("Summarize this
# document ...", "make notes ...").
_INSTRUCTION_LEAD_RE = re.compile(
    r"^\s*(please\s+)?(summari[sz]e|make|create|save|add|write|draft|compare|"
    r"take\s+notes|note|find|search|get|show|list|export)\b[\s,:-]*",
    re.IGNORECASE,
)
# Quoted entity spans (paper titles). 6+ chars to avoid matching stray quotes.
_QUOTED_SPAN_RE = re.compile(r"[\"“”']([^\"“”']{6,})[\"“”']")


def _coerce_text(content: Any) -> str:
    """Flatten a possibly-multimodal HumanMessage.content into plain text.

    ``content`` may be a list of content blocks; the raw value was previously
    used directly and any downstream ``.lower()/.split()`` would raise.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return " ".join(parts)
    return str(content or "")


def _build_search_query(raw: str) -> str:
    """Derive a focused retrieval query from a raw user message.

    Trace 019ea8f0 fed the retriever the whole message — three quoted paper
    titles glued to "make notes and save them" — as one literal query. It
    embedded to a degenerate centroid that matched nothing, and the
    instruction tokens diluted lexical search. Prefer the quoted entity names
    (what the user actually wants retrieved); otherwise strip a leading
    imperative clause. Fall back to the raw text when nothing structured is
    found.
    """
    if not raw:
        return raw
    quoted = _QUOTED_SPAN_RE.findall(raw)
    if quoted:
        return " ".join(q.strip() for q in quoted)[:512]
    cleaned = _INSTRUCTION_LEAD_RE.sub("", raw).strip()
    return (cleaned or raw)[:512]


# ---------------------------------------------------------------------------
# RAG node
# ---------------------------------------------------------------------------


@track_node_execution("rag_node")
async def rag_node(state: AgentState, config: RunnableConfig) -> dict:
    """Retrieve relevant documents via hybrid search and store in state."""
    # Lazy import — graph.py owns the project-id text extractor.
    from src.services.agent.graph import _extract_project_id_from_text

    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    # Find the last user message to use as search query
    last_user_msg: Optional[str] = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = _coerce_text(msg.content)
            break

    # Fast-path: skip retrieval entirely for short, clearly-conversational
    # queries (e.g. "hi", "thanks!"). Saves an embedding + hybrid search call
    # and avoids injecting ~935 retrieval tokens into the system prompt.
    #
    # Earlier revision gated the skip on "no project context to propagate".
    # That gate made every short query in an active project trigger RAG
    # (observed trace 019e168a: "hi" in ML-in-Health-Care project pulled
    # 5 chunks from sibling Copilot productivity PDFs and used 7152 input
    # tokens). Project context still propagates via current_project_id +
    # page_context — we only suppress the RAG chunk injection itself.
    page_context = dict(state.get("page_context") or {})
    existing_project_id = state.get("current_project_id") or page_context.get(
        "project_id"
    )
    if last_user_msg and not _is_retrieval_query(last_user_msg):
        logger.debug(
            "rag_node: skipping retrieval for conversational query: %r",
            last_user_msg[:80],
        )
        # Still surface a UUID extracted from the text or carried in state
        # so downstream nodes can act on the project context.
        extracted_pid = _extract_project_id_from_text(last_user_msg or "")
        resolved_pid: Optional[str] = _resolve_active_project_id(
            existing_project_id, extracted_pid
        )
        state_update: Dict[str, Any] = {"retrieved_contexts": []}
        if resolved_pid:
            state_update["current_project_id"] = resolved_pid
            if (
                page_context.get("project_id") != resolved_pid
                or page_context.get("type") != "project"
            ):
                state_update["page_context"] = {
                    **page_context,
                    "type": "project",
                    "project_id": resolved_pid,
                }
        return state_update

    # Extract a project UUID from the latest user message (e.g. a pasted
    # /projects/<uuid> URL) so downstream nodes carry the context across
    # turns without depending on the client always re-sending page_context.
    extracted_pid = _extract_project_id_from_text(last_user_msg or "")

    resolved_project_id: Optional[str] = _resolve_active_project_id(
        existing_project_id, extracted_pid
    )
    state_update: Dict[str, Any] = {}
    if resolved_project_id:
        state_update["current_project_id"] = resolved_project_id
        # Mirror into page_context so the system prompt built by llm_node
        # tells the LLM about the active project, and any tool that reads
        # page_context (e.g. list_project_documents) can resolve it.
        # When a project is resolved, force type="project" — otherwise the
        # llm_node falls into the "chat" branch and never tells the LLM that
        # a project is active. This is what was happening when users named
        # a project in plain text after the CLI sent type="chat".
        needs_update = (
            page_context.get("project_id") != resolved_project_id
            or page_context.get("type") != "project"
        )
        if needs_update:
            page_context = {
                **page_context,
                "type": "project",
                "project_id": resolved_project_id,
            }
            state_update["page_context"] = page_context

    if not last_user_msg or not current_user:
        return {"retrieved_contexts": [], **state_update}

    # Clean the retrieval query: drop instruction clauses, prefer quoted
    # entity names. Keep last_user_msg raw for project-id/intent checks above.
    search_query = _build_search_query(last_user_msg)

    # Test-time injection still supported.
    search_fn = configurable.get("search_fn")
    if search_fn:
        try:
            contexts = await search_fn(search_query, str(current_user.id))
            return {"retrieved_contexts": contexts, **state_update}
        except Exception as e:
            logger.warning("injected search_fn failed", exc_info=e)
            return {"retrieved_contexts": [], **state_update}

    # Skip the org-wide knowledge-base read when no project context is
    # active. Trace 019e191a showed a chat-mode "Find recent transformer
    # papers" query pull 5 chunks of unrelated Copilot productivity PDFs
    # — the org KB indexes every project's docs, so without a project
    # filter the chunks are noise that bloats input by ~10k chars. The
    # agent will use search_arxiv/search_documents for explicit lookup.
    if not resolved_project_id:
        logger.debug(
            "rag_node: skipping DO KB read — no active project context"
        )
        return {"retrieved_contexts": [], **state_update}

    # Production retrieval: DO KB primary, hybrid search fallback.
    # Pass resolved_project_id so KB results stay scoped to the active project
    # — org-scoped KB otherwise leaks chunks from sibling projects.
    primary_contexts: Optional[List[dict]] = await _try_primary_do_kb_read(
        search_query, current_user, project_id=resolved_project_id
    )
    if primary_contexts:
        return {"retrieved_contexts": primary_contexts, **state_update}

    contexts = await _legacy_hybrid_search_fallback(search_query, current_user)
    return {"retrieved_contexts": contexts, **state_update}


__all__ = [
    "_is_retrieval_query",
    "_shape_do_kb_context",
    "_try_primary_do_kb_read",
    "_legacy_hybrid_search_fallback",
    "rag_node",
]
