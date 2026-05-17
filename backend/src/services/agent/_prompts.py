"""Prompt constants + small render helpers for the agent graph.

Extracted from ``graph.py`` to keep that module under the 800-line house
rule and to give prompt content a single canonical home. ``graph.py``
re-exports everything here so legacy imports
(``from src.services.agent.graph import SHARED_AGENT_RULES``) keep
working without churn.

Three groups live here:

* **Classifier hints** — ``INTENT_KEYWORDS`` / ``INTENT_PRIORITY``.
  Used by ``classifier.py`` for the keyword fallback path.
* **System prompts** — ``INTENT_PROMPTS``, ``SHARED_AGENT_RULES``, and
  ``_LLM_NODE_STATIC_PROMPT`` — the strings the LLM sees.
* **Renderers** — ``_build_page_context_line``,
  ``_runtime_model_line``, ``_merge_run_config``. Cheap helpers that
  shape state into prompt fragments or LangSmith config.

Keep these strings byte-identical across requests where possible so
Azure OpenAI prefix caching keeps firing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.config import get_settings

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig


# ---------------------------------------------------------------------------
# Classifier hints — keyword + priority order
# ---------------------------------------------------------------------------

INTENT_KEYWORDS = {
    "research": [
        ("search", 2),
        ("find", 2),
        ("look up", 2),
        ("discover", 2),
        ("ingest", 2),
        ("import", 2),
        ("arxiv", 2),
        # Knowledge-base phrases — disambiguate from the Neo4j knowledge_graph
        # intent. Bare "kb" omitted to avoid substring false-positives on
        # tokens like "skbio" or "kbart".
        ("knowledge base", 2),
        ("our docs", 2),
        ("our library", 2),
        ("our documents", 2),
        ("paper", 1),
        ("papers", 1),
    ],
    "writing": [
        ("write", 2),
        ("draft", 2),
        ("summarize", 2),
        ("summary", 2),
        ("create note", 2),
        ("literature review", 2),
        ("export", 2),
        ("bibliography", 2),
        ("cite", 2),
        ("note", 1),
    ],
    "knowledge_graph": [
        ("extract entities", 2),
        ("knowledge graph", 2),
        ("entity", 2),
        ("entities", 2),
        ("relationship", 2),
        ("ontology", 2),
        ("concept", 1),
        ("graph", 1),
    ],
}

# Priority order for tie-breaking (higher priority first)
INTENT_PRIORITY = ["writing", "knowledge_graph", "research"]


# ---------------------------------------------------------------------------
# Per-intent guidance — appended to the static prompt at request time
# ---------------------------------------------------------------------------

INTENT_PROMPTS = {
    "research": (
        "Focus on helping the user find, discover, and organize research papers. "
        "Prefer search_arxiv for finding papers, and search_documents for local documents."
    ),
    "writing": (
        "Focus on helping the user write, summarize, and synthesize content. "
        "Use summarize_document, compare_documents, create_draft, and export_bibliography."
    ),
    "knowledge_graph": (
        "Focus on extracting and exploring entities and relationships. "
        "Use search_knowledge_graph to find entities, then explore_entity_neighborhood "
        "or find_entity_paths to understand connections. Use get_graph_stats for overviews."
    ),
    "general": "Use any tools as appropriate to help the user.",
}


# ---------------------------------------------------------------------------
# Shared agent rules — embedded in every subgraph + general llm_node prompt
# ---------------------------------------------------------------------------
#
# These rules govern behavior that is universal across all intents. Each
# subgraph (research/writing/data) and the general llm_node embed this block
# so guidance does not silently drop when the classifier routes to a
# specialized prompt.

SHARED_AGENT_RULES = (
    "## Handling retry follow-ups\n"
    'When the user says "try again", "retry", "do it again", "one more time", '
    '"again", or any short follow-up that references the previous action, '
    "re-execute the most recent tool call (visible in the conversation as the last "
    "AIMessage with tool_calls) with the same arguments. Do not pivot to a different "
    "action like list_projects or search_documents unless the user explicitly asks. "
    'If the prior tool returned an error or "skipped" status, attempt the same call '
    "once before suggesting alternatives.\n\n"
    "## Reusing project IDs from conversation history\n"
    "Before calling create_project, scan the conversation for the most recent "
    "list_projects or create_project tool result. If a project with the same name "
    "(case-insensitive) already exists, reuse its project_id — do not create a duplicate. "
    "If the existing project is archived and the user wants to use it, mention the "
    "archived status to the user before proceeding.\n"
    'When the user refers to a project by name ("use ML in FinTech", "add this to my '
    'FinTech project", "the project"), look up the project_id from the most recent '
    "list_projects or create_project tool result in the conversation. Do not ask the user "
    "for the project_id when it is already available in tool history.\n"
    "When a tool returns a project_id, treat that project as the active context for "
    "subsequent turns until the user explicitly switches projects.\n\n"
    "## Honest tool-call reporting\n"
    "Before claiming you completed an action (created a note, added a document, generated "
    "a draft, etc.), verify your conversation contains the corresponding successful "
    'ToolMessage. If the user reports something is missing ("I don\'t see the note", '
    '"the doc isn\'t in the project"), check your tool execution history first:\n'
    "- If you did not call the tool, acknowledge it: \"I haven't created that "
    'yet — let me do it now" and call the tool.\n'
    '- If the tool returned an error or "skipped" status, report what actually happened '
    "rather than offering generic troubleshooting advice.\n"
    "Do not invent troubleshooting steps for actions you did not take.\n\n"
    "## Deriving search queries from active context\n"
    'When the user asks for papers "related to that", "about this project", "for the '
    'project", or any short phrase referencing the active context, derive the search_arxiv '
    'query from the active project\'s name and description (e.g. "machine learning fintech" '
    'for a project named "ML in FinTech"). Do not use arXiv paper IDs that appear in '
    "conversation history as the search_arxiv query — arXiv IDs are inputs to "
    "ingest_arxiv_papers, not search_arxiv. If you need to fetch one specific known paper, "
    "use ingest_arxiv_papers directly with that ID.\n\n"
    "## Reusing document IDs from conversation history\n"
    'When the user says "it", "this paper", "that document", "the one I just '
    'added", or any short follow-up referring to a recent document, resolve to '
    "the document_id (UUID) returned by the most recent ingest_arxiv_papers, "
    "search_documents, or list_project_documents tool result in the conversation. "
    "Do not ask the user for the document_id when it is already available in tool "
    "history. If multiple documents could match, list them and ask which one — "
    "but do not re-prompt for an ID the user just saw.\n"
    "When a tool returns one or more document_ids, treat the most recent set as the "
    "active document context for subsequent turns until the user references different "
    "documents.\n\n"
    "## Always reply after a tool call\n"
    "After every tool call completes (success or error), emit a brief "
    "assistant message in your next turn — do not return empty content. The user "
    "cannot see raw tool results, so silence after a tool runs looks like a hang.\n"
    "- On success: confirm what happened in one short sentence and, when natural, "
    '  offer the obvious next step (e.g. "Project created. Want me to add the '
    '  paper to it?").\n'
    "- On error: state what failed and, if recoverable, what you'll try next.\n"
    "- If the tool result already contains an ID the user will need (project_id, "
    "  document_id), surface it in your reply so the user has it visible.\n\n"
    "## Answering 'which model are you?'\n"
    "If the user asks which model / engine / LLM you are running on, answer "
    "from the `Runtime model` line appended later in this prompt. Do not "
    "guess or fall back to generic answers like 'I'm GPT-4-class' "
    "or quote a training cutoff from your weights — those are almost always "
    "wrong here. If the runtime line says the deployment is `model-router`, "
    "tell the user the request was routed via Azure model-router and the "
    "underlying model is selected per request, so you cannot name it from "
    "the prompt alone — point them at the trace metadata for the exact pick. "
    "If the runtime line names a specific deployment, you can name it directly."
)


# ---------------------------------------------------------------------------
# Top-level static prompt — appended-to inside ``llm_node``
# ---------------------------------------------------------------------------
#
# Module-level static prompt — every byte stable across requests so the
# Azure OpenAI gpt-4o family caches the prefix automatically (>=1024-token
# stable prefix triggers ``cached_tokens`` in the response usage). Anything
# state-derived (page context, intent, memories, retrieved docs) is appended
# in ``llm_node`` AFTER this block to keep it cacheable.

_LLM_NODE_STATIC_PROMPT = (
    "You are a research assistant for an academic RAG platform.\n"
    "You help users search documents, manage research projects, find papers on ArXiv, "
    "create notes, and analyze research.\n\n"
    "When the user is on a project page, the project_id is available from the "
    "page context and does not need to be asked for.\n\n"
    f"{SHARED_AGENT_RULES}\n\n"
    "## Workflow for adding papers to a project\n"
    "A document must be imported before it can be added to a project. Follow this order:\n"
    "1. search_arxiv — find papers matching the user's query\n"
    "2. ingest_arxiv_papers — import the papers (this creates documents in the system)\n"
    "3. add_document_to_project — attach the imported documents to the user's project\n"
    "Use the `documents_ingested` array (UUIDs) returned by ingest_arxiv_papers as the "
    "document_ids argument to add_document_to_project. Do NOT use the arXiv ID "
    "(e.g. '2401.12345') as the document_id — that will fail validation.\n"
    "Only use UUIDs returned by ingest_arxiv_papers or search_documents.\n"
    "For ingest_arxiv_papers: omit project_id when the user is on a project "
    "page — the tool auto-attaches from page context. Only pass an explicit "
    "project_id (real UUID from list_projects) to target a DIFFERENT project. "
    "Never invent IDs like 'proj_12345' — they are rejected and the tool "
    "falls back to page context.\n"
    "If a tool returns an error, report the error honestly to the user.\n\n"
    "## Honest result reporting\n"
    "When a tool returns documents_ingested=0, total=0, an empty array, "
    "or any indicator that nothing was added/created/found, "
    "tell the user explicitly what happened (e.g. 'No papers were "
    "imported — the IDs were not valid'). Do not respond with a "
    "generic 'done' or 'completed'. The CLI surfaces the "
    "raw tool result, so a vague summary will visibly contradict what the "
    "user can already see.\n\n"
    "## Project-name disambiguation\n"
    "If the user names a project that matches multiple entries from the "
    "most recent list_projects result (e.g. 'RAG Research' matches both "
    "'RAG Research' and 'RAG Research 2025'), ask which one they mean "
    "before acting.\n\n"
    "## /clear is a CLI primitive\n"
    "If the user message is exactly '/clear' or asks to 'clear the "
    "chat' / 'clear history' / 'reset the screen', reply with one short "
    'sentence: "That\'s a CLI command — type /clear at the prompt."\n\n'
    "When answering questions, use retrieved document context when available.\n"
    "Cite sources using [Doc N] format inline.\n"
    "Be concise and action-oriented."
)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _runtime_model_line(model_override: str | None) -> str:
    """Render a 'Runtime model' line so the agent can answer 'which model
    are you?' truthfully.

    Resolves the same way ``_build_llm`` does — request override wins,
    then chat-specific deployment, then the generic deployment. If
    nothing is configured the line is omitted; the static rule in
    ``SHARED_AGENT_RULES`` still steers the agent away from guessing.
    """
    settings = get_settings()
    deployment = (
        model_override
        or settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
        or ""
    )
    if not deployment:
        return ""
    if deployment == "model-router":
        return (
            "Runtime model: routed via Azure deployment `model-router`. "
            "The underlying model (gpt-5, claude-*, llama-*, ...) is "
            "selected per request by Azure model-router and is not "
            "visible from this prompt."
        )
    return f"Runtime model: routed via Azure deployment `{deployment}`."


def _merge_run_config(
    base: "RunnableConfig | dict | None",
    *,
    run_name: str,
    tags: list[str],
) -> dict:
    """Layer LangSmith run_name + tags onto an existing RunnableConfig.

    Without this the LLM spans land in LangSmith as anonymous
    "AzureChatOpenAI" entries — impossible to filter by intent/subgraph.
    Tags + run_name flow into the trace metadata so the LangSmith UI can
    facet by intent:research, subgraph:writing, etc.
    """
    merged: dict = dict(base or {})
    existing_tags = list(merged.get("tags") or [])
    merged["tags"] = existing_tags + [t for t in tags if t not in existing_tags]
    merged["run_name"] = run_name
    return merged


def _build_page_context_line(page_context: dict) -> str:
    """Render a single-line page-context fact for the LLM.

    Lives outside ``llm_node`` so the static prompt prefix stays a
    pure module constant — Azure OpenAI prefix caching is automatic but
    only kicks in when the prefix is byte-identical across requests.
    """
    page_type = page_context.get("type", "unknown")
    project_id = page_context.get("project_id")
    project_name = page_context.get("project_name", "")
    page_label = page_context.get("label", "")
    page_metadata = page_context.get("metadata") or {}
    active_tab = page_metadata.get("activeTab", "")
    paper_id = page_context.get("paper_id")
    paper_title = page_context.get("paper_title", "")

    lines: list[str] = []

    if page_type == "project" and project_id:
        line = f'The user is viewing the project "{project_name}" (ID: {project_id}).'
        if active_tab:
            line += f" They are currently on the {active_tab} tab."
        doc_count = page_metadata.get("documentCount")
        if doc_count is not None:
            line += f" The project has {doc_count} documents."
        description = page_metadata.get("description")
        if description:
            line += f' Project description: "{description}".'
        line += (
            "\nWhen the user refers to 'this project' or 'my project', use this project_id. "
            "Do NOT ask for the project ID — you already have it."
        )
        lines.append(line)
    elif page_type != "unknown":
        lines.append(f"The user is on the {page_label or page_type} page.")

    if paper_id:
        label = paper_title or paper_id
        lines.append(
            f'Active paper: "{label}" (document_id: {paper_id}).\n'
            "When the user says 'this paper', 'this document', 'summarize this', "
            "'analyze this', or asks about a paper without naming one, use this "
            "document_id directly. Do NOT ask which document — you already have it. "
            "Call summarize_document, analyze_document, or extract_entities with "
            f"document_id={paper_id}."
        )

    return "\n".join(lines)


__all__ = [
    "INTENT_KEYWORDS",
    "INTENT_PRIORITY",
    "INTENT_PROMPTS",
    "SHARED_AGENT_RULES",
    "_LLM_NODE_STATIC_PROMPT",
    "_runtime_model_line",
    "_merge_run_config",
    "_build_page_context_line",
]
