"""LangGraph agent graph definition.

Builds a ``StateGraph`` that chains:
  START -> rag_node -> llm_node -> [conditional] -> tool_node -> llm_node (loop) | END
"""

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

# Matches a UUID anywhere in a string. Used to extract project IDs from URLs
# or raw UUIDs that the user pastes into the conversation so the agent can
# carry the context forward across turns.
from src.services.agent._uuid import UUID_SEARCH_RE as _UUID_RE


def _extract_project_id_from_text(text: str) -> Optional[str]:
    """Return the first project UUID found in *text*, preferring ``/projects/<uuid>``.

    Falls back to any standalone UUID in the text. Returns ``None`` if no
    UUID is present.
    """
    if not text:
        return None
    project_url_match = re.search(
        r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if project_url_match:
        return project_url_match.group(1).lower()
    bare_match = _UUID_RE.search(text)
    return bare_match.group(1).lower() if bare_match else None


from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph


_TOOL_PLACEHOLDER_CONTENT = '{"status": "skipped"}'


def _tool_call_id(tc: Any) -> Optional[str]:
    """Extract the ``id`` field from a tool_call entry, tolerating dict or attr form."""
    if isinstance(tc, dict):
        tc_id = tc.get("id")
    else:
        tc_id = getattr(tc, "id", None)
    return tc_id if isinstance(tc_id, str) and tc_id else None


def _sanitize_messages(raw: list) -> list:
    """Ensure the message list is valid for LLM APIs.

    OpenAI-compatible chat APIs require:
    1. Every assistant message with ``tool_calls`` must be IMMEDIATELY
       followed by ``ToolMessage`` entries answering each call.
    2. Every ``ToolMessage`` must follow an assistant message whose
       ``tool_calls`` includes its ``tool_call_id``.

    Real-world checkpoint state can violate both invariants — e.g. a
    cancelled tool execution leaves an unanswered ``tool_call``, or a
    HumanMessage gets inserted between an AI's tool_calls and the
    ToolMessages answering them. We rebuild the message list defensively:

    - Index every ``ToolMessage`` by its ``tool_call_id`` (last wins).
    - Walk the raw list, skipping standalone ToolMessages — they're
      re-emitted right after their parent AIMessage (or replaced with a
      ``"skipped"`` placeholder if no real one exists).
    - ToolMessages whose ``tool_call_id`` doesn't match any AI tool_call
      are dropped — they're orphans that confuse the API.
    - Consecutive HumanMessages are merged into one (LangGraph state
      occasionally appends them separately on retries / interrupts).

    The placeholder content stays ``'{"status": "skipped"}'`` because
    the compactor recognises that exact string to skip synthetic items.
    """
    # Pass 1: index ToolMessages by tool_call_id (last occurrence wins)
    tm_by_id: dict[str, ToolMessage] = {}
    for msg in raw:
        if isinstance(msg, ToolMessage) and msg.tool_call_id:
            tm_by_id[msg.tool_call_id] = msg

    # Pass 2: rebuild list, putting each AI's ToolMessages right after it
    rebuilt: list = []
    placed_tm_ids: set[str] = set()
    for msg in raw:
        if isinstance(msg, ToolMessage):
            # Standalone TMs are re-inserted via their parent AI (below)
            # or dropped if no parent claims them.
            continue
        rebuilt.append(msg)
        if not (isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None)):
            continue
        for tc in msg.tool_calls:
            tc_id = _tool_call_id(tc)
            if not tc_id or tc_id in placed_tm_ids:
                continue
            tm = tm_by_id.get(tc_id)
            if tm is None:
                tm = ToolMessage(
                    content=_TOOL_PLACEHOLDER_CONTENT, tool_call_id=tc_id
                )
            rebuilt.append(tm)
            placed_tm_ids.add(tc_id)

    # Pass 3: collapse consecutive HumanMessages.
    #
    # When a previous turn is interrupted (CancelledError from the user
    # aborting the stream by typing a new message), the unanswered
    # HumanMessage stays in the checkpoint. The next user input arrives
    # as a second consecutive HumanMessage. The previous concatenation
    # behavior caused the LLM to see both as a single combined intent
    # (trace 019e1885: "Find recent transformer papers" + "hi" → LLM
    # answered the older cancelled query). Treat consecutive Human
    # messages as supersession: keep only the latest. The earlier
    # message had no AI response, so the user clearly abandoned it.
    merged: list = []
    for msg in rebuilt:
        if (
            merged
            and isinstance(merged[-1], HumanMessage)
            and isinstance(msg, HumanMessage)
        ):
            merged[-1] = msg
        else:
            merged.append(msg)
    return merged


from langgraph.types import RetryPolicy, interrupt, Command

from src.core.config import get_settings
from src.core.openai_endpoint import classify_openai_endpoint
from src.services.agent.compactor import make_compactor_node
from src.services.agent.error_recovery import (
    ToolError,
    classify_error,
    classify_error_from_payload,
    retry_transient,
)
from src.services.agent.observability import track_node_execution
from src.services.agent.planner import make_planner_node
from src.services.agent.reflection import make_reflection_gate
from src.services.agent.state import AgentState
from src.services.agent.tools import ALL_TOOLS

# Lazy reference for execute_tool (avoids circular import, enables patching)
execute_tool = None  # type: ignore[assignment]
_default_execute_tool = None  # type: ignore[assignment]
_execute_tool_lock = threading.Lock()


def _get_execute_tool():
    """Lazily import execute_tool and keep it patch-friendly.

    The agent tests patch both ``src.services.agent.graph.execute_tool`` and
    the backward-compatible re-export at ``src.api.agent.execute.execute_tool``.
    After the API split, caching the first imported callable caused later
    re-export patches to be ignored. We only refresh the cached callable when
    graph.py is still pointing at the last default import.
    """
    global execute_tool, _default_execute_tool  # noqa: PLW0603

    with _execute_tool_lock:
        if execute_tool is None:
            from src.api.agent.execute import execute_tool as _et

            execute_tool = _et
            _default_execute_tool = _et
            return execute_tool

        from src.api.agent.execute import execute_tool as _et

        if execute_tool is _default_execute_tool:
            execute_tool = _et
            _default_execute_tool = _et

        return execute_tool


logger = logging.getLogger(__name__)

MAX_TOOL_LOOPS = 10


def _safe_json_loads(s: str) -> Any:
    """Parse JSON, returning a fallback dict if parsing fails."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {"raw": s}


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards in untrusted strings.

    Storage keys come from the DO Knowledge Base API — an external service.
    Backslash escapes both ``%`` (multi-char wildcard) and ``_`` (single
    char) so a malformed/malicious key cannot broaden the suffix match.
    Use with ``Column.like(pattern, escape='\\\\')``.
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# LLM construction
# ---------------------------------------------------------------------------

_LLM_CACHE: dict[tuple[str, str], BaseChatModel] = {}


def _build_llm(model_override: str | None = None):
    """Build a LangChain chat model from the existing Azure/OpenAI config.

    ``model_override`` lets a per-request deployment name win over the configured
    default — used to make the agent honor ``request.model`` from the API.

    Clients are cached by ``(endpoint_type, deployment)`` to avoid rebuilding
    the HTTP client on every ``llm_node`` invocation (~30-50 ms each).
    """
    settings = get_settings()

    endpoint = (
        settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT or ""
    )
    api_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY or ""
    api_version = (
        settings.AZURE_OPENAI_CHAT_API_VERSION or settings.AZURE_OPENAI_API_VERSION
    )
    deployment = (
        model_override
        or settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
    )

    if not endpoint or not api_key:
        raise RuntimeError(
            "Azure/OpenAI chat endpoint and API key must be configured. "
            "Set AZURE_OPENAI_CHAT_ENDPOINT + AZURE_OPENAI_CHAT_API_KEY "
            "(or the non-CHAT variants)."
        )

    if not deployment:
        raise RuntimeError(
            "Chat deployment name must be configured. Set "
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME (or AZURE_OPENAI_DEPLOYMENT_NAME)."
        )

    endpoint_type = classify_openai_endpoint(endpoint)
    cache_key = (endpoint_type, deployment)
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    # All gpt-5 family deployments (gpt-5, gpt-5-mini, gpt-5-nano, etc.)
    # reject custom temperature — Azure returns 400. Drop it for the whole
    # family rather than per-deployment allowlist.
    temperature = None if deployment.startswith("gpt-5") else 0.7

    # gpt-5 family supports reasoning_effort to trade reasoning depth for
    # latency. Defaults to "low" for fast agent loops; raise via settings
    # for harder reasoning tasks. Non-gpt-5 deployments ignore this kwarg.
    reasoning_effort = settings.AGENT_MAIN_REASONING_EFFORT
    is_gpt5_family = deployment.startswith("gpt-5") if deployment else False

    # Force Chat Completions API. langchain-openai auto-routes gpt-5 family
    # with reasoning_effort to the Azure Responses API, which currently rejects
    # the agent's tool_call message history with "Unsupported data type". The
    # Chat Completions path handles tool_calls reliably and supports
    # reasoning_effort on gpt-5 deployments via api-version 2024-10-21+.
    # Bound LLM call wall-clock + cap retries. Prevents the model-router hang
    # observed in LangSmith (traces with end_time=null blocking root 70s+).
    request_timeout = settings.AGENT_LLM_REQUEST_TIMEOUT
    max_retries = settings.AGENT_LLM_MAX_RETRIES

    if endpoint_type == "openai_compatible":
        from langchain_openai import ChatOpenAI

        kwargs: dict = dict(
            model=deployment,
            api_key=api_key,
            base_url=endpoint,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = ChatOpenAI(**kwargs)
    else:
        from langchain_openai import AzureChatOpenAI

        kwargs = dict(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_tokens=4096,
            use_responses_api=False,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if is_gpt5_family and reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        llm = AzureChatOpenAI(**kwargs)

    _LLM_CACHE[cache_key] = llm
    return llm


# ---------------------------------------------------------------------------
# Memory nodes
# ---------------------------------------------------------------------------


# Memory recall/save nodes now live in _nodes_memory. Re-export so
# legacy imports (`from src.services.agent.graph import memory_save_node`)
# keep working without rewriting tests/callers.
from src.services.agent._nodes_memory import (  # noqa: E402
    memory_retrieval_node,
    memory_save_node,
)


# ---------------------------------------------------------------------------
# Graph nodes
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

        from sqlalchemy import select

        from src.core.database import AsyncSessionLocal
        from src.models.document import Document
        from src.models.organization import Organization
        from src.services.do_kb import get_do_kb_client

        async with AsyncSessionLocal() as session:
            org = await session.get(Organization, org_id)
            kb_uuid = getattr(org, "do_kb_uuid", None) if org else None
            if not kb_uuid:
                return None

            client = get_do_kb_client()
            result = await client.retrieve(kb_uuid=kb_uuid, query=query, top_k=5)
            if not result.chunks:
                return None

            storage_keys = {c.document_id for c in result.chunks if c.document_id}
            title_by_key: dict[str, tuple[str, str]] = {}
            if storage_keys:
                # DO KB returns ``metadata.item_name`` as the leaf filename
                # only (e.g. ``<doc_id>.txt``) while ``Document.storage_path``
                # stores the full canonical key
                # (``documents/{org}/{doc_id}.{ext}``). Match by suffix so
                # both legacy and canonical layouts resolve.
                from sqlalchemy import or_

                filters = [Document.storage_path == k for k in storage_keys]
                filters += [
                    Document.storage_path.like(f"%/{_escape_like(k)}", escape="\\")
                    for k in storage_keys
                ]
                rows = await session.execute(
                    select(Document.id, Document.storage_path, Document.title)
                    .where(Document.organization_id == org_id)
                    .where(or_(*filters))
                )
                for doc_id, storage_path, title in rows:
                    if storage_path in storage_keys:
                        leaf = storage_path
                    else:
                        leaf = storage_path.rsplit("/", 1)[-1] if storage_path else ""
                    title_by_key[leaf] = (str(doc_id), title or leaf)

            # Project scoping: drop chunks whose resolved document is not in
            # the active project. Org-scoped KB returns sibling-project hits
            # (observed trace 019e168a: "ML in Health Care" query returned
            # Copilot productivity PDFs). Filter via collection_documents.
            chunks_to_emit = result.chunks
            # Safety: project requested but ZERO chunks resolved to known
            # documents → don't leak unscoped chunks. Force fallback so the
            # legacy hybrid search runs with its own org-scope guarantees.
            if project_id and not title_by_key and result.chunks:
                logger.info(
                    "do_kb_read: %d chunks unresolvable to org documents under "
                    "project scope %s — returning None to trigger fallback",
                    len(result.chunks),
                    project_id,
                )
                return None
            if project_id and title_by_key:
                from uuid import UUID as _UUID

                from src.models.collection import CollectionDocument

                resolved_doc_ids = {
                    _UUID(doc_id) for doc_id, _ in title_by_key.values() if doc_id
                }
                if resolved_doc_ids:
                    try:
                        pid = _UUID(project_id)
                    except (ValueError, TypeError):
                        pid = None
                    if pid is not None:
                        membership_rows = await session.execute(
                            select(CollectionDocument.document_id).where(
                                CollectionDocument.collection_id == pid,
                                CollectionDocument.document_id.in_(resolved_doc_ids),
                            )
                        )
                        in_project = {str(r[0]) for r in membership_rows}
                        chunks_to_emit = [
                            c
                            for c in result.chunks
                            if (title_by_key.get(c.document_id or "", (None, None))[0] or "")
                            in in_project
                        ]
                        if not chunks_to_emit:
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


async def _legacy_hybrid_search_fallback(
    query: str, current_user
) -> List[dict]:
    """Fallback to hybrid search when DO KB is unavailable or returns nothing."""
    try:
        from src.models.search_schemas import SearchQuery
        from src.services.search.hybrid_search_service import hybrid_search_service

        search_request = SearchQuery(
            query=query,
            limit=5,
            search_type="hybrid",
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


@track_node_execution("rag_node")
async def rag_node(state: AgentState, config: RunnableConfig) -> dict:
    """Retrieve relevant documents via hybrid search and store in state."""
    configurable = config.get("configurable", {})
    current_user = configurable.get("current_user")

    # Find the last user message to use as search query
    last_user_msg: Optional[str] = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
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
        resolved_pid: Optional[str] = (
            extracted_pid or existing_project_id or None
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

    resolved_project_id: Optional[str] = extracted_pid or existing_project_id or None
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

    # Test-time injection still supported.
    search_fn = configurable.get("search_fn")
    if search_fn:
        try:
            contexts = await search_fn(last_user_msg, str(current_user.id))
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
        last_user_msg, current_user, project_id=resolved_project_id
    )
    if primary_contexts:
        return {"retrieved_contexts": primary_contexts, **state_update}

    contexts = await _legacy_hybrid_search_fallback(last_user_msg, current_user)
    return {"retrieved_contexts": contexts, **state_update}


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

# Weighted keywords: (keyword, weight)
# Action verbs get higher weight; ambiguous nouns get lower weight
# Classifier hints live in _prompts; re-exported here so legacy imports
# (`from src.services.agent.graph import INTENT_KEYWORDS, INTENT_PRIORITY`)
# keep working without churn.
from src.services.agent._prompts import (  # noqa: E402  (re-export)
    INTENT_KEYWORDS,
    INTENT_PRIORITY,
)


def _extract_prior_tool(messages: List[Any]) -> Optional[Dict[str, Any]]:
    """Walk *messages* backwards and return the most recent tool call.

    Returns a dict with keys ``name``, ``args``, and ``result`` (the matching
    ToolMessage content as a string), or ``None`` if no tool call exists in
    the conversation. Used to pass retry context to the intent classifier so
    short follow-ups like "try again" route to the same intent as the prior
    tool.
    """
    for ai_idx in range(len(messages) - 1, -1, -1):
        msg = messages[ai_idx]
        if not isinstance(msg, AIMessage):
            continue
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        first = tool_calls[0]
        tool_call_id = first.get("id")
        result = ""
        # Only scan AFTER the AIMessage we found — otherwise a stale
        # ToolMessage from a previous turn that happens to share an id
        # (or a synthetic placeholder) gets returned, misleading the
        # classifier about what just happened.
        for follow in messages[ai_idx + 1 :]:
            if isinstance(follow, ToolMessage) and follow.tool_call_id == tool_call_id:
                result = str(follow.content)
                break
        return {
            "name": first.get("name", ""),
            "args": first.get("args", {}) or {},
            "result": result,
        }
    return None


async def _classify_core(state: AgentState, config: RunnableConfig) -> dict:
    """Classify user intent using LLM with keyword fallback.

    Used directly inside ``preprocessing_node`` (which composes its own
    parallel tracking) and indirectly via ``intent_classifier_node``,
    which wraps this with ``@track_node_execution`` for callers that
    invoke it as a graph node.
    """
    from src.services.agent.classifier import classify_intent_with_fallback

    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg:
        return {"intent": "general", "intent_confidence": 0.0}

    previous_turn = ""
    found_user = False
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            if found_user:
                break
            found_user = True
            continue
        if found_user and isinstance(msg, AIMessage) and msg.content:
            previous_turn = msg.content
            break

    prior_tool = _extract_prior_tool(state["messages"])
    page_context = config.get("configurable", {}).get("page_context", {})
    result = await classify_intent_with_fallback(
        query=last_user_msg,
        page_context=page_context,
        previous_turn=previous_turn,
        prior_tool=prior_tool,
    )
    logger.debug(
        "Classified intent: %s (confidence=%.2f, source=%s)",
        result.intent,
        result.confidence,
        result.source,
    )
    try:
        from src.services.agent.observability import record_classifier_source

        record_classifier_source(source=result.source, intent=result.intent)
    except Exception:
        pass
    return {"intent": result.intent, "intent_confidence": result.confidence}


# ``intent_classifier_node`` is the tracked graph-node version of
# ``_classify_core``. Production wiring uses ``_classify_core`` directly via
# ``preprocessing_node``; the tracked alias is kept for tests and any future
# wiring that wants the per-node Prometheus metrics.
intent_classifier_node = track_node_execution("intent_classifier_node")(_classify_core)


@track_node_execution("preprocessing_node")
async def preprocessing_node(state: AgentState, config: RunnableConfig) -> dict:
    """Run RAG retrieval, intent classification, and memory retrieval in parallel.

    Also resets per-turn ephemeral state (``plan``, ``reflection_count``,
    ``_reflection_result``, ``tool_loop_count``, ``error_count``,
    ``user_confirmed``) so that values carried over from the previous turn
    via the checkpointer cannot:

    - block the planner from re-planning against the new query (H-11);
    - trigger a spurious revision at the start of the next turn from a
      stale ``_reflection_result`` (H-01 / M-06);
    - bypass the destructive-tool HITL gate via a stale ``user_confirmed``
      flag (H-17);
    - count this turn's first error against last turn's accumulated
      ``error_count``.
    """
    rag_task = asyncio.create_task(rag_node(state, config))
    classify_task = asyncio.create_task(_classify_core(state, config))
    memory_task = asyncio.create_task(memory_retrieval_node(state, config))

    results = await asyncio.gather(
        rag_task, classify_task, memory_task, return_exceptions=True
    )

    defaults = [
        {"retrieved_contexts": []},
        {"intent": "general", "intent_confidence": 0.0},
        {"user_memories": []},
    ]
    merged: dict = {
        # Per-turn resets — must come BEFORE merging subtask results so a
        # subtask that explicitly sets one of these keys still wins.
        "plan": [],
        "reflection_count": 0,
        "_reflection_result": None,
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "last_error_info": {},
        "user_confirmed": False,
        "pending_confirmation": {},
    }
    for result, default in zip(results, defaults):
        if isinstance(result, Exception):
            logger.warning("Preprocessing subtask failed: %s", result)
            merged.update(default)
        else:
            merged.update(result)
    return merged


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate sub-graph based on classified intent."""
    intent = state.get("intent", "general")
    if intent == "research":
        return "research_subgraph"
    if intent == "writing":
        return "writing_subgraph"
    if intent == "knowledge_graph":
        return "data_subgraph"
    return "llm_node"


# ---------------------------------------------------------------------------
# Intent-specific tool subsets and prompt augmentations
# ---------------------------------------------------------------------------

RESEARCH_TOOLS_NAMES = {
    "search_arxiv",
    "ingest_arxiv_papers",
    "search_documents",
    "create_project",
    "list_projects",
    "add_document_to_project",
    "list_project_documents",
    "execute_code",
}
WRITING_TOOLS_NAMES = {
    "create_draft",
    "create_project_note",
    "export_bibliography",
    "summarize_document",
    "compare_documents",
}
KG_TOOLS_NAMES = {
    "extract_entities",
    "search_knowledge_graph",
    "explore_entity_neighborhood",
    "find_entity_paths",
    "get_graph_stats",
    "search_documents",
    "execute_code",
}

# Subset for "general" intent — avoids binding all 20 tools on every first
# message (greetings, "help", etc.) which bloats the token budget by ~4 000
# tokens. Research/writing/KG intents get their own targeted subsets via the
# sub-graphs. General gets the 10 most commonly used discovery+productivity
# tools; more specialised tools (create_draft, compare_documents, etc.) are
# available once the classifier narrows the intent.
GENERAL_TOOLS_NAMES = {
    "search_arxiv",
    "ingest_arxiv_papers",
    "search_documents",
    "create_project",
    "list_projects",
    "add_document_to_project",
    "list_project_documents",
    "create_project_note",
    "summarize_document",
    "search_knowledge_graph",
}

# Intent prompts + shared rules + static prompt now live in _prompts.py.
# Re-export so subgraphs and tests that did
# `from src.services.agent.graph import SHARED_AGENT_RULES`
# keep working without rewriting every caller.
from src.services.agent._prompts import (  # noqa: E402
    INTENT_PROMPTS,
    SHARED_AGENT_RULES,
    _LLM_NODE_STATIC_PROMPT,
    _build_page_context_line,
    _merge_run_config,
    _runtime_model_line,
)



@track_node_execution("llm_node")
async def llm_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the LLM with system prompt, RAG context, and bound tools."""
    page_context = state.get("page_context", {})
    retrieved = state.get("retrieved_contexts", [])

    # Static prefix first — must be byte-identical across requests so the
    # provider's automatic prefix cache hits on every turn after the first.
    # Dynamic state-derived content goes AFTER the prefix below.
    dynamic_parts: list[str] = []

    context_line = _build_page_context_line(page_context)
    if context_line:
        dynamic_parts.append(context_line)

    intent = state.get("intent", "general")
    intent_guidance = INTENT_PROMPTS.get(intent, INTENT_PROMPTS["general"])
    dynamic_parts.append(f"Current intent: {intent}. {intent_guidance}")

    runtime_line = _runtime_model_line(state.get("model") or None)
    if runtime_line:
        dynamic_parts.append(runtime_line)

    user_memories = state.get("user_memories", [])
    if user_memories:
        mem_text = "\n".join(
            f"- {m.get('value', {}).get('query', '')}"
            for m in user_memories
            if m.get("value")
        )
        if mem_text.strip():
            dynamic_parts.append(f"Relevant past interactions:\n{mem_text}")

    if retrieved:
        context_text = "\n\n".join(
            f"[Doc {i + 1}] {ctx['title']}:\n{ctx['content']}"
            for i, ctx in enumerate(retrieved)
        )
        dynamic_parts.append(f"Retrieved context:\n{context_text}")

    system_text = _LLM_NODE_STATIC_PROMPT
    if dynamic_parts:
        system_text += "\n\n" + "\n\n".join(dynamic_parts)

    sanitized = _sanitize_messages(list(state["messages"]))
    messages = [SystemMessage(content=system_text)] + sanitized

    # Bind intent-specific tool subset
    intent_tools = _get_tools_for_intent(intent)

    # Lightweight model selection. Two cases use gpt-5-mini instead of
    # full gpt-5:
    #
    # 1. Post-tool synthesis turn (last message is ToolMessage) — heavy
    #    reasoning already happened before the tool call; this turn is
    #    pure prose synthesis. Saves ~5-15s.
    #
    # 2. intent="general" turn (no project/research/writing context).
    #    "hi", "thanks", capability questions, small talk — gpt-5 burns
    #    ~700 reasoning tokens deciding whether to call a tool. gpt-5-mini
    #    handles these in 2-3s. Trace 019e19f2: "hi" took 13s on gpt-5.
    #
    # Both cases gated by AGENT_LIGHTWEIGHT_SYNTHESIS so a single env var
    # disables the optimization if quality regresses.
    settings = get_settings()
    last_is_tool_msg = bool(sanitized) and isinstance(sanitized[-1], ToolMessage)
    use_lightweight = settings.AGENT_LIGHTWEIGHT_SYNTHESIS and (
        last_is_tool_msg or intent == "general"
    )
    if use_lightweight:
        from src.services.agent.llm_factory import build_synthesis_llm

        llm = build_synthesis_llm(max_tokens=4096)
        logger.debug(
            "llm_node: using synthesis model (intent=%s, last_is_tool=%s)",
            intent,
            last_is_tool_msg,
        )
    else:
        llm = _build_llm(model_override=state.get("model") or None)
    # parallel_tool_calls=False forces gpt-5 to emit one tool_call per turn.
    # Trace 019e18f0 showed 13+ parallel search_arxiv calls when this was
    # implicitly True — agent never got a chance to see the first result
    # before issuing more searches.
    llm_with_tools = llm.bind_tools(
        intent_tools,
        parallel_tool_calls=settings.AGENT_PARALLEL_TOOL_CALLS,
    )
    invoke_config = _merge_run_config(
        config, run_name=f"llm_node:{intent}", tags=[f"intent:{intent}", "subgraph:main"]
    )
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages, config=invoke_config),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "llm_node: LLM exceeded %ds (intent=%s); emitting fallback",
            AGENT_LLM_TIMEOUT_SECONDS,
            intent,
        )
        return {
            "messages": [
                AIMessage(
                    content=(
                        "The model took too long to respond. Please try again "
                        "or rephrase your request."
                    ),
                ),
            ],
            "last_error": "llm_timeout",
            "error_count": state.get("error_count", 0) + 1,
        }

    return {
        "messages": [response],
    }


# Tool execution + interrupt + concurrency constants now live in
# _nodes_tools. Re-export so legacy imports
# (`from src.services.agent.graph import tool_node, interrupt_node,
# DESTRUCTIVE_TOOLS, AGENT_LLM_TIMEOUT_SECONDS, TOOL_TIMEOUT_SECONDS,
# make_filtered_tool_node`) keep working without rewriting subgraphs/tests.
from src.services.agent._nodes_tools import (  # noqa: E402
    AGENT_LLM_TIMEOUT_SECONDS,
    DESTRUCTIVE_TOOLS,
    TOOL_TIMEOUT_SECONDS,
    _execute_single_tool,
    _get_tool_semaphore,
    _NO_OUTER_RETRY_TOOLS,
    _SLOW_TOOL_TIMEOUT_SECONDS,
    _SLOW_TOOLS,
    interrupt_node,
    make_filtered_tool_node,
    tool_node,
)


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


MAX_ERRORS = 3


def should_continue(state: AgentState) -> str:
    """Decide whether to route to tool_node, interrupt_node, or reflection_gate (then END)."""
    # Bail out if too many errors have accumulated
    if state.get("error_count", 0) >= MAX_ERRORS:
        logger.warning(
            "Agent reached max error count (%d), stopping. Last error: %s",
            MAX_ERRORS,
            state.get("last_error", ""),
        )
        return "reflection_gate"

    last = state["messages"][-1] if state["messages"] else None
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("tool_loop_count", 0) < MAX_TOOL_LOOPS
    ):
        # Check if any tool call is destructive — route through interrupt
        has_destructive = any(tc["name"] in DESTRUCTIVE_TOOLS for tc in last.tool_calls)
        if has_destructive:
            return "interrupt_node"
        return "tool_node"
    return "reflection_gate"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def after_interrupt(state: AgentState) -> str:
    """Route after interrupt: proceed to tool_node if confirmed, else reflection gate and end."""
    if state.get("user_confirmed", False):
        return "tool_node"
    return "reflection_gate"


_RETRY_POLICY = RetryPolicy(max_attempts=3)


def build_agent_graph() -> StateGraph:
    """Build the uncompiled agent state graph.

    Flow:
      START -> preprocessing_node (RAG + classify + memory in parallel)
        -> [route_by_intent]
        -> research_subgraph | writing_subgraph | data_subgraph | general path

      General path:
        planner_node -> llm_node -> [should_continue]
          -> tool_node -> compactor_node -> llm_node (loop)
          -> interrupt_node -> [after_interrupt] -> tool_node | reflection_gate
          -> reflection_gate -> [reflection_route] -> memory_save_node | llm_node (revise)

      Sub-graphs (internal planner + compactor + reflection) -> memory_save_node -> END
    """
    from src.services.agent.subgraphs.data_agent import build_data_subgraph
    from src.services.agent.subgraphs.research_agent import build_research_subgraph
    from src.services.agent.subgraphs.writing_agent import build_writing_subgraph

    # General-path v2 nodes
    tool_names = [t.name for t in ALL_TOOLS]
    planner_node_fn = make_planner_node(tool_names)
    compactor_node_fn = make_compactor_node()
    reflection_node_fn, reflection_route_fn = make_reflection_gate()

    graph = StateGraph(AgentState)

    graph.add_node("preprocessing_node", preprocessing_node)
    graph.add_node("planner_node", planner_node_fn)
    graph.add_node("llm_node", llm_node, retry=_RETRY_POLICY)
    graph.add_node("tool_node", tool_node)
    graph.add_node("compactor_node", compactor_node_fn)
    graph.add_node("interrupt_node", interrupt_node)
    graph.add_node("reflection_gate", reflection_node_fn)
    graph.add_node("memory_save_node", memory_save_node, retry=_RETRY_POLICY)

    # Sub-graphs compiled as nodes (they have internal planner/compactor/reflection)
    graph.add_node("research_subgraph", build_research_subgraph().compile())
    graph.add_node("writing_subgraph", build_writing_subgraph().compile())
    graph.add_node("data_subgraph", build_data_subgraph().compile())

    graph.set_entry_point("preprocessing_node")

    # Route by intent after parallel preprocessing
    graph.add_conditional_edges(
        "preprocessing_node",
        route_by_intent,
        {
            "research_subgraph": "research_subgraph",
            "writing_subgraph": "writing_subgraph",
            "data_subgraph": "data_subgraph",
            "llm_node": "planner_node",
        },
    )

    # Sub-graphs (with internal reflection) -> memory_save_node -> END
    graph.add_edge("research_subgraph", "memory_save_node")
    graph.add_edge("writing_subgraph", "memory_save_node")
    graph.add_edge("data_subgraph", "memory_save_node")

    # General path: planner -> llm
    graph.add_edge("planner_node", "llm_node")

    # General path: llm_node -> conditional
    graph.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node": "tool_node",
            "interrupt_node": "interrupt_node",
            "reflection_gate": "reflection_gate",
        },
    )
    graph.add_conditional_edges(
        "interrupt_node",
        after_interrupt,
        {"tool_node": "tool_node", "reflection_gate": "reflection_gate"},
    )

    # General path: tool_node -> compactor_node -> llm_node (loop)
    graph.add_edge("tool_node", "compactor_node")
    graph.add_edge("compactor_node", "llm_node")

    # Reflection gate routes: proceed -> memory_save, revise -> llm_node
    graph.add_conditional_edges(
        "reflection_gate",
        reflection_route_fn,
        {"proceed": "memory_save_node", "revise": "llm_node"},
    )
    graph.add_edge("memory_save_node", END)

    return graph


def compile_agent_graph(checkpointer=None, store=None, **kwargs):
    """Compile the agent graph, optionally with a checkpointer and store.

    ``checkpointer`` may be ``None`` (no checkpointing), an instance of
    ``BaseCheckpointSaver``, or ``True`` to opt into the default in-memory
    saver. Anything else is rejected with a clear error rather than
    silently passing a bool to ``graph.compile()`` (which would crash with
    ``AttributeError`` deep inside LangGraph at runtime).

    ``store`` is an optional ``BaseStore`` for long-term, cross-thread
    memory (user preferences, facts).  When provided, LangGraph injects it
    into nodes that accept a ``Runtime`` parameter so they can use
    ``runtime.store`` instead of importing the singleton directly.
    """
    graph = build_agent_graph()
    from langgraph.checkpoint.base import BaseCheckpointSaver

    compile_kwargs: dict = {}
    if store is not None:
        compile_kwargs["store"] = store

    if checkpointer is None or checkpointer is False:
        return graph.compile(**compile_kwargs)

    if checkpointer is True:
        # Convenience: ``True`` opts into the in-memory default so callers
        # don't have to import MemorySaver themselves.
        from langgraph.checkpoint.memory import MemorySaver

        return graph.compile(checkpointer=MemorySaver(), **compile_kwargs)

    if isinstance(checkpointer, BaseCheckpointSaver):
        return graph.compile(checkpointer=checkpointer, **compile_kwargs)

    raise TypeError(
        "compile_agent_graph(checkpointer=...) must be None, True, False, "
        f"or a BaseCheckpointSaver instance — got {type(checkpointer).__name__}"
    )


def create_graph():
    """No-arg entry point for langgraph dev (langgraph.json)."""
    return compile_agent_graph(checkpointer=True)
